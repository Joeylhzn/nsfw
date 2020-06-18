# -*- coding: utf-8 -*-
import os
import re
import time
import asyncio
import logging
import threading

import requests
import pyppeteer

from urllib.parse import urljoin

from lxml import etree
from Crypto.Cipher import AES

from config import DEFAULT_HEADERS, ALLOW_STATUS, DOWNLOAD_DIR


def make_valid_filename(filename, suffix=".mp4"):
    if os.name == "nt":
        if len(filename) > 200:
            filename = filename[:-4][:50] + "..."
        return filename.translate(
            str.maketrans(dict.fromkeys(' \\ / : * ? " < > |'.split(), ""))
        ) + suffix
    return filename + suffix


class BaseSpider:

    name = "base"

    def __init__(self, q):
        self.q = q

        self.tasks = 0
        self.filename = "undefined"
        self.download_path = "undefined"
        self.failed_parts = []
        self.failed_times = {}

        self.mutex = threading.Lock()
        self.all_tasks_done = threading.Condition(self.mutex)
        self.init()

    def init(self):
        self.download_path = DOWNLOAD_DIR + os.sep + self.name
        os.makedirs(self.download_path, exist_ok=True)

    def log(self, info, level=logging.INFO):
        self.q.put((level, info))

    def task_done(self):
        with self.all_tasks_done:
            self.tasks -= 1
            if self.tasks == 0:
                self.all_tasks_done.notify_all()

    def tasks_done(self):
        with self.all_tasks_done:
            if self.tasks:
                self.all_tasks_done.wait()
        while self.failed_parts:
            part = self.failed_parts.pop()
            self.thread_download(part, retry_flag=True)
        self.log(f"{self.filename} Done")

    def run(self, *args, **kwargs):
        raise NotImplementedError

    @staticmethod
    def xpath(html, path):
        if not isinstance(html, etree._Element):
            return None
        targets = html.xpath(path)
        return targets[0] if targets else None

    def get_html(self, url, headers=DEFAULT_HEADERS, params=None,
                 repeat=3, stream=False, need_content=False):
        r = None
        while repeat > 0:
            try:
                r = requests.get(url, headers=headers, params=params,
                                 stream=stream)
            except requests.exceptions.ConnectionError:
                repeat -= 1
                time.sleep(3)
                self.log(f"get {url} failed, retry!")
                continue
            else:
                break
        if r and r.status_code in ALLOW_STATUS:
            return r.content if need_content else r
        return None

    def download(self, *args, **kwargs):
        video_url, self.filename, base_url, *_ = args
        max_workers = kwargs.get("max_workers", 4)
        self.tasks = max_workers
        r = requests.head(video_url, headers=DEFAULT_HEADERS)
        content_length = int(r.headers.get("Content-Length", 0))
        if content_length:
            with open(self.filename, "wb") as f:
                f.write(b'\0' * content_length)
            part_size, rest_size = divmod(content_length, max_workers)
            for i in range(max_workers):
                start = part_size * i
                end = start + part_size - 1 if i != (max_workers - 1) \
                    else content_length
                threading.Thread(
                    target=self.thread_download,
                    args=(start, end, video_url, self.filename)
                ).start()
        else:
            self.log(f"can not find content length: {base_url}")
            video = self.get_html(video_url, stream=True)
            if not video:
                self.log(f"download failed: {video_url},\n"
                         f"source: {base_url}", logging.WARNING)
                return None
            with open(self.filename, "wb") as f:
                for chunk in video.iter_content(chunk_size=8192):
                    f.write(chunk)
        self.tasks_done()

    def thread_download(self, *args, **kwargs):
        start, end, url, filename = args
        headers = {'Range': 'bytes=%d-%d' % (start, end)}
        headers.update(DEFAULT_HEADERS)
        r = self.get_html(url, headers=headers, stream=True)
        if r:
            with open(filename, "r+b") as f:
                f.seek(start)
                try:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
                except requests.exceptions.ChunkedEncodingError:
                    self.failed_parts.append(args)
                    self.log(f"download failed: {url}", logging.ERROR)
        else:
            self.failed_parts.append(args)
        if not kwargs.get("retry_flag", False):
            self.task_done()


class M3U8Spider(BaseSpider):

    KEY = re.compile(r"#EXT-X-KEY:METHOD=(?P<method>.*),URI=\"(?P<uri>.*)\"")

    def run(self, *args, **kwargs):
        raise NotImplementedError

    def merge(self):
        if self.files and self.filename:
            with open(self.filename, "wb") as f:
                for data in self.files:
                    if not data:
                        self.log("没有正确下载部分ts文件")
                        return None
                    f.write(data)
                    f.flush()

    def tasks_done(self):
        with self.all_tasks_done:
            self.all_tasks_done.wait()
        self.merge()
        self.log(f"{self.filename} Done")

    def download(self, m3u8, max_workers=10):
        r = self.get_html(m3u8)
        if not r:
            return None
        content = r.text.split("\n")
        download_urls, key_uri, key, count = [], "", "", 0
        for index, line in enumerate(content):
            if '#EXT-X-KEY' in line:
                g = self.KEY.match(line)
                key_uri = g.group("uri")
            elif "EXTINF" in line:
                download_urls.append(
                    (count, urljoin(m3u8, content[index + 1]))
                )
                count += 1

        if key_uri:
            key = self.get_html(key_uri, need_content=True)
        per_thread_tasks, left = divmod(len(download_urls), max_workers)
        self.tasks = max_workers
        self.files = [b"\0"] * len(download_urls)
        for i in range(max_workers):
            threading.Thread(
                target=self.thread_download,
                args=(key, download_urls[i*per_thread_tasks:
                                         (i+1)*per_thread_tasks])
            ).start()
        if left:
            threading.Thread(target=self.thread_download,
                             args=(key, download_urls[-left:])).start()
            self.tasks += 1
        self.tasks_done()

    def thread_download(self, key, download_urls):
        for item in download_urls:
            index, url = item
            res = self.get_html(url, need_content=True)
            if key:
                cryptor = AES.new(key, AES.MODE_CBC, key)
                res = cryptor.decrypt(res)
            self.files[index] = res
        with self.all_tasks_done:
            self.tasks -= 1
            if self.tasks == 0:
                self.all_tasks_done.notify_all()
