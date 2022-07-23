# -*- coding: utf-8 -*-
import re
import logging
import subprocess
import tempfile

import cloudscraper

from lxml import etree

from .base import make_valid_filename, M3U8Spider, DEFAULT_HEADERS


LST_QUALITY = ["1080", "720", "480", "240"]


class Spider(M3U8Spider):

    name = "jable"

    SOURCE = re.compile(r".*hlsUrl = \'(.*)\';")

    def run(self, url):
        r = self.get_cloudflare_html(url)
        if not r:
            return None
        html = etree.HTML(r.text)
        target = self.xpath(html, r'/html/head/meta[@property="og:title"]/@content')
        if not target:
            return None
        self.filename = make_valid_filename(self.download_path, target.strip())
        url_info = self.xpath(html, r'//section[@class="pb-3 pb-e-lg-30"]/script[2]/text()')
        if not url_info:
            self.log(f"can not get hls url", logging.ERROR)
            return None
        hls_url = self.SOURCE.match(url_info.strip()).group(1)
        self.log(f"got video url {hls_url},\ndownload path is {self.filename}")
        self.download(hls_url)
