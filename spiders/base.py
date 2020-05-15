# -*- coding: utf-8 -*-
import os
import logging
import threading

import requests

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
        self.all_task_done = threading.Event()
        self.mutex = threading.Lock()
        self.init()

    def init(self):
        self.download_path = DOWNLOAD_DIR + os.sep + self.name
        if not os.path.exists(self.download_path):
            os.mkdir(self.download_path)

    def log(self, info, level=logging.INFO):
        self.q.put((level, info))

    def unfinished(self):
        with self.mutex:
            return self.tasks

    def task_done(self):
        while self.unfinished():
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
        max_worker = kwargs.get("max_worker", 4)
        self.tasks = max_worker + 1
        r = requests.head(video_url, headers=DEFAULT_HEADERS)
        content_length = int(r.headers.get("Content-Length", 0))
        if content_length:
            with open(self.filename, "wb") as f:
                f.write(b'\0' * content_length)
            part_size, rest_size = divmod(content_length, max_worker)
            for i in range(max_worker):
                start = part_size * i
                end = start + part_size
                threading.Thread(target=self.thread_download, args=(start, end, video_url, self.filename)).start()
            if rest_size:
                threading.Thread(target=self.thread_download,
                                 args=(content_length - rest_size, content_length, video_url, self.filename)).start()
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
        with self.mutex:
            self.tasks -= 1
        self.all_task_done.set()
