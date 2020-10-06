# -*- coding: utf-8 -*-
import os
import logging

from urllib.parse import urlparse

from .base import M3U8Spider, make_valid_filename


class Spider(M3U8Spider):

    name = "hanime"

    HEADERS = {
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/81.0.4044.138 Safari/537.36",
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
        self.filename = make_valid_filename(self.download_path, title)
        self.log(f"{self.name} spider run, download path is {self.filename}")
        self.download(m3u8)
