# -*- coding: utf-8 -*-
import os


__all__ = [
    "DEFAULT_HEADERS", "LOGGER_DIR", "DOWNLOAD_DIR",
    "LOGGING_CONF", "PROXIES", "ALLOW_STATUS"
]

DIRNAME = os.getcwd()
DOWNLOAD_DIR = DIRNAME + os.sep + "download"
LOGGER_DIR = DIRNAME + os.sep + "log"

DEFAULT_HEADERS = {
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                  "(KHTML, like Gecko) Chrome/103.0.5060.114 Safari/537.36 Edg/103.0.1264.62"
}
PROXIES = {}
ALLOW_STATUS = [200, 206, 304]

LOGGING_CONF = {
    "version": 1,
    "formatters": {
        "simple": {
            "format": '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": "INFO",
            "formatter": "simple",
        },
        "file": {
            "class": "logging.FileHandler",
            "level": "INFO",
            "formatter": "simple",
            "filename": LOGGER_DIR + os.sep + "log.log",
            "encoding": "utf-8"
        }
    },
    "loggers": {
        "nsfw": {
            "level": "INFO",
            "handlers": ["file", "console"],
            "propagate": False
        },
    },
    "root": {
        "level": "DEBUG",
        "handlers": ["console"]
    }
}
