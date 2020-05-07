# -*- coding: utf-8 -*-
import os
import signal
import atexit
import logging
import logging.config
import importlib
import multiprocessing

from urllib.parse import urlparse
from functools import partial
from concurrent.futures import ProcessPoolExecutor

from config import LOGGING_CONF, DOWNLOAD_DIR, LOGGER_DIR


spiders = {}


def log_process(q):
    logging.config.dictConfig(LOGGING_CONF)
    logger = logging.getLogger("nsfw")
    logger.info("start logging")
    while True:
        msg = q.get()
        if isinstance(msg, str) and msg == "quit":
            logger.info("quit logging")
            break
        else:
            level, log = msg
            logger.log(level, log)


def run(url, q):
    _, netloc, *_ = urlparse(url)
    net = netloc.split(".")[-2]
    if net not in spiders:
        try:
            lib = importlib.import_module(f"spiders.{net}")
        except ImportError:
            q.put((logging.ERROR, f"暂不支持{net}类型爬虫"))
            return None
        spiders[net] = lib.Spider(q)
    spider = spiders[net]
    spider.run(url)


def init():
    for _dir in [DOWNLOAD_DIR, LOGGER_DIR]:
        if not os.path.exists(_dir):
            os.mkdir(_dir)


def main(urls, queue, max_workers=os.cpu_count()-1):
    init()
    multiprocessing.Process(target=log_process, args=(queue, ), daemon=True).start()
    pool = ProcessPoolExecutor(max_workers=max_workers)
    run_with_queue = partial(run, q=queue)
    with pool as p:
        p.map(run_with_queue, urls)
    atexit.register(lambda q: q.put("quit"), queue)


if __name__ == "__main__":
    queue = multiprocessing.Manager().Queue()
    urls = [
        # 目标网址
    ]
    main(urls, queue)
