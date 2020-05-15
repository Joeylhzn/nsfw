# -*- coding: utf-8 -*-
import os
import re
import logging
import threading

from urllib.parse import urlparse

from Crypto.Cipher import AES

from .base import BaseSpider, make_valid_filename


class Spider(BaseSpider):

    name = "hanime"

    KEY = re.compile(r"#EXT-X-KEY:METHOD=(?P<method>.*),URI=\"(?P<uri>.*)\"")
    HEADERS = {
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.138 Safari/537.36",
        "x-session-token": "",
        "x-signature": "",
        "x-signature-version": "web2",
        "x-time": "0",
        "x-token": "null"
    }

    def run(self, url):
        _, title = urlparse(url).path.rsplit("/", 1)

        json_url = "https://hanime.tv/rapi/v7/videos_manifests" + f"/{title}?"

        r = self.get_html(json_url, headers=self.HEADERS)
        if not r:
            self.log(f"没有获取到正确的json路径:{url}", logging.WARNING)
            return None
        m3u8 = ""
        j = r.json()
        j_data = j["videos_manifest"]["servers"][0]["streams"]
        for data in j_data:
            if data["kind"] == "hls":
                m3u8 = data["url"]
                break
        self.filename = self.download_path + os.sep + make_valid_filename(title)
        self.log(f"{self.name} spider run, download path is {self.filename}")
        self.download(m3u8, self.filename)

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
        while self.unfinished():
            self.all_task_done.wait()
        self.merge()
        self.log(f"{self.filename} Done")

    def download(self, m3u8, filename):
        r = self.get_html(m3u8)
        if not r:
            return None
        content = r.text.split("\n")  # 获取第一层M3U8文件内容
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
        self.tasks = len(download_urls)
        self.files = [b"\0"] * self.tasks
        per_thread_tasks, left = divmod(self.tasks, 10)
        for i in range(10):
            threading.Thread(target=self.thread_download, args=(key, download_urls[i*10: (i+1)*10])).start()
        if left:
            threading.Thread(target=self.thread_download, args=(key, download_urls[-left:]))
        self.task_done()

    def thread_download(self, key, download_urls):
        for item in download_urls:
            index, url = item
            res = self.get_html(url, need_content=True)
            if key:
                cryptor = AES.new(key, AES.MODE_CBC, key)
                self.files[index] = cryptor.decrypt(res)
                with self.mutex:
                    self.tasks -= 1
                self.all_task_done.set()
