# -*- coding: utf-8 -*-
import os
import queue
import logging
import logging.config
import importlib
import threading
import multiprocessing

import click

from urllib.parse import urlparse
from functools import partial
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

from config import LOGGING_CONF, DOWNLOAD_DIR, LOGGER_DIR
from notification import NotifyMsg, notifier


spiders = {}


def log_process(q):
    logging.config.dictConfig(LOGGING_CONF)
    logger = logging.getLogger("nsfw")
    logger.info("start logging")
    while True:
        msg = q.get()
        if isinstance(msg, str) and msg == "quit":
            logger.info("quit logging")
        elif isinstance(msg, NotifyMsg):
            notifier.notify(msg)
        else:
            level, log = msg
            logger.log(level, log)
        q.task_done()


def run(url, q):
    if not url:
        q.put((logging.WARNING, f"wrong format url: {url}"))
        return None
    _, netloc, *_ = urlparse(url)
    net = netloc.split(".")[-2]
    if net not in spiders:
        try:
            lib = importlib.import_module(f"spiders.{net}")
        except ImportError:
            q.put((logging.WARNING, f"暂不支持{net}类型爬虫"))
            return None
        spiders[net] = lib
    spider = spiders[net].Spider(q)
    spider.run(url)


def init():
    for _dir in [DOWNLOAD_DIR, LOGGER_DIR]:
        if not os.path.exists(_dir):
            os.mkdir(_dir)


@click.command()
@click.option("-U", "--urls", multiple=True, help="目标网站(用空格划分)")
@click.option("-F", "--file", help="从文件中读取目标网站")
@click.option("-M", "--multi", type=click.Choice(['process', 'thread']),
              default="thread", help="多进程还是多线程")
@click.option("-W", "--workers", default=os.cpu_count()-1, help="pool大小")
def main(urls, file, multi, workers):
    init()
    if urls:
        urls = [url.strip() for url in urls]
    elif file:
        with open(file, "r", encoding="utf-8", errors="ignore") as f:
            urls = list(map(str.strip, filter(lambda x: x.strip(),
                                              f.readlines())))
    else:
        raise Exception("urls or file should be provided")

    if multi == "process" and os.name != "nt":
        q = multiprocessing.Manager().Queue()
        multiprocessing.Process(target=log_process, args=(q, ),
                                name="log-process", daemon=True).start()
        pool = ProcessPoolExecutor(max_workers=workers)
    else:
        q = queue.Queue()
        threading.Thread(target=log_process, args=(q,), name="log-thread",
                         daemon=True).start()
        pool = ThreadPoolExecutor(max_workers=workers)
    run_with_queue = partial(run, q=q)
    with pool as p:
        res = p.map(run_with_queue, urls)
    for r in res:
        if r:
            q.put((logging.WARNING, r))
    q.put("quit")
    q.join()


if __name__ == "__main__":
    main()
    # todo: https://www.youporn.com/
