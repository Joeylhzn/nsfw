# -*- coding: utf-8 -*-
import os
import atexit
import logging
import argparse
import threading

import requests

from config import DEFAULT_HEADERS, ALLOW_STATUS


def parse_args():
    parser = argparse.ArgumentParser(description='nsfw')

    parser.add_argument(dest='filenames', metavar='filename', nargs='*')

    parser.add_argument('-S', '--search', metavar='pattern', required=True,
                        dest='patterns', action='append',
                        help='text pattern to search for')

    parser.add_argument('-v', dest='verbose', action='store_true',
                        help='verbose mode')

    parser.add_argument('-o', dest='outfile', action='store',
                        help='output file')
    return parser.parse_args()


def make_valid_filename(filename):
    if os.name == "nt":
        if len(filename) > 200:
            filename = filename[:-4][:50] + "..." + ".mp4"
        return filename.translate(str.maketrans(dict.fromkeys(' \\ / : * ? " < > |'.split(), "")))
    return filename


class BaseSpider:
    def __init__(self, q):
        self.q = q
        self.init()

    def init(self):
        raise NotImplementedError

    def log(self, info, level=logging.INFO):
        self.q.put((level, info))

    def run(self, *args, **kwargs):
        raise NotImplementedError

    @staticmethod
    def get_html(url, headers=DEFAULT_HEADERS, params=None, stream=False):
        r = requests.get(url, headers=headers, params=params, stream=stream)
        if r and r.status_code in ALLOW_STATUS:
            return r
        return None

    def download(self, *args, **kwargs):
        video_url, filename, base_url, *_ = args
        max_worker = kwargs.get("max_worker", 4)
        r = requests.head(video_url, headers=DEFAULT_HEADERS)
        content_length = int(r.headers.get("Content-Length", 0))
        if content_length:
            with open(filename, "wb") as f:
                f.write(b'\0' * content_length)
            part_size, rest_size = divmod(content_length, max_worker)
            for i in range(max_worker):
                start = part_size * i
                end = start + part_size
                threading.Thread(target=self.thread_download, args=(start, end, video_url, filename)).start()
            threading.Thread(target=self.thread_download,
                             args=(content_length - rest_size, content_length, video_url, filename)).start()
        else:
            video = self.get_html(video_url, stream=True)
            if not video:
                self.log(f"download failed: {video_url},\nsource: {base_url}", logging.WARNING)
                return None
            with open(filename, "wb") as f:
                for chunk in video.iter_content(chunk_size=1024 * 1024):
                    f.write(chunk)
                    f.flush()
        atexit.register(self.log, f"{filename} Done")

    def thread_download(self, start, end, url, filename):
        headers = {'Range': 'bytes=%d-%d' % (start, end)}
        headers.update(DEFAULT_HEADERS)
        r = self.get_html(url, headers=headers, stream=True)
        with open(filename, "r+b") as f:
            f.seek(start)
            f.write(r.content)
