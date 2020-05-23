# -*- coding: utf-8 -*-
import os
import re
import logging
import threading

import requests

from Crypto.Cipher import AES

from config import DEFAULT_HEADERS, ALLOW_STATUS, DOWNLOAD_DIR


def make_valid_filename(filename, suffix=".mp4"):
    if os.name == "nt":
        if len(filename) > 200:
            filename = filename[:-4][:50] + "..."
        return filename.translate(str.maketrans(dict.fromkeys(' \\ / : * ? " < > |'.split(), ""))) + suffix
    return filename + suffix


class BaseSpider:

    name = "base"

    def __init__(self, q):
        self.q = q
        self.tasks = 0
        self.filename = "undefined"
        self.download_path = "undefined"
        self.mutex = threading.Lock()
        self.all_task_done = threading.Condition(self.mutex)
        self.init()

    def init(self):
        self.download_path = DOWNLOAD_DIR + os.sep + self.name
        os.makedirs(self.download_path, exist_ok=True)

    def log(self, info, level=logging.INFO):
        self.q.put((level, info))

    def unfinished(self):
        with self.mutex:
            print("unlocked")
            return self.tasks

    def task_done(self):
        with self.all_task_done:
            self.all_task_done.wait()
        self.log(f"{self.filename} Done")

    def run(self, *args, **kwargs):
        raise NotImplementedError

    @staticmethod
    def get_html(url, headers=DEFAULT_HEADERS, params=None, stream=False, need_content=False):
        r = requests.get(url, headers=headers, params=params, stream=stream)
        if r and r.status_code in ALLOW_STATUS:
            if need_content:
                return r.content
            return r
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
                end = start + part_size
                threading.Thread(target=self.thread_download, args=(start, end, video_url, self.filename)).start()
            if rest_size:
                threading.Thread(target=self.thread_download,
                                 args=(content_length - rest_size, content_length, video_url, self.filename)).start()
                self.tasks += 1
        else:
            video = self.get_html(video_url, stream=True)
            if not video:
                self.log(f"download failed: {video_url},\nsource: {base_url}", logging.WARNING)
                return None
            with open(self.filename, "wb") as f:
                for chunk in video.iter_content(chunk_size=1024 * 1024):
                    f.write(chunk)
                    f.flush()
        self.task_done()

    def thread_download(self, *args, **kwargs):
        start, end, url, filename = args
        headers = {'Range': 'bytes=%d-%d' % (start, end)}
        headers.update(DEFAULT_HEADERS)
        r = self.get_html(url, headers=headers, stream=True)
        if r:
            with open(filename, "r+b") as f:
                f.seek(start)
                f.write(r.content)
        with self.all_task_done:
            self.tasks -= 1
            if self.tasks == 0:
                self.all_task_done.notify_all()


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

    def task_done(self):
        with self.all_task_done:
            self.all_task_done.wait()
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
                download_urls.append((count, content[index + 1]))
                count += 1

        if key_uri:
            key = self.get_html(key_uri, need_content=True)
        per_thread_tasks, left = divmod(len(download_urls), max_workers)
        self.tasks = max_workers
        self.files = [b"\0"] * len(download_urls)
        for i in range(max_workers):
            threading.Thread(target=self.thread_download,
                             args=(key, download_urls[i*per_thread_tasks: (i+1)*per_thread_tasks])).start()
        if left:
            threading.Thread(target=self.thread_download, args=(key, download_urls[-left:])).start()
            self.tasks += 1
        self.task_done()

    def thread_download(self, key, download_urls):
        for item in download_urls:
            index, url = item
            res = self.get_html(url, need_content=True)
            if key:
                cryptor = AES.new(key, AES.MODE_CBC, key)
                res = cryptor.decrypt(res)
            self.files[index] = res
        with self.all_task_done:
            self.tasks -= 1
            if self.tasks == 0:
                self.all_task_done.notify_all()
