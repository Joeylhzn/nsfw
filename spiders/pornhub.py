# -*- coding: utf-8 -*-
import os
import re
import uuid
import logging
import logging.config
import subprocess
import tempfile

from lxml import etree

from .base import make_valid_filename, BaseSpider


class Spider(BaseSpider):

    name = "pornhub"

    LST_QUALITY = ["1080p", "720p", "480p", "240p"]
    DOWNLOAD_URL_PATTERNS = {
        k: v for k, v in
        zip(LST_QUALITY, map(re.compile, [fr"quality_{quality}:\s?'(.*?)',?" for quality in LST_QUALITY]))
    }
    VIDEO_TITLE_PATTERN = re.compile(r"video_title:\s?'(.*?)',")
    FLASHVARS_PATTERN = re.compile(r"flashvars.*?=")

    def run(self, url):
        js_codes, param = self.get_js_codes(url)
        if not js_codes or not param:
            self.log(f"{url} can not find target js code", logging.WARNING)
            return None
        with tempfile.NamedTemporaryFile(mode="w", suffix=".js") as f:
            for code in js_codes:
                f.write(code)
            f.write(f"console.log({param})")
            f.seek(0)
            flashvars = subprocess.check_output(["node", f.name]).decode("utf-8")
        if not flashvars:
            self.log(f"{url} can not parse js code", logging.WARNING)
            return None
        info = self.parse_info(flashvars)
        if not all(info):
            return None
        video_url, quality, filename = info
        self.log(f"got video url {video_url},\nquality is {quality},\ndownload path is {filename}")
        self.download(video_url, filename, url, max_worker=10)

    def get_js_codes(self, url):
        js_codes = []
        obj = self.get_html(url)
        if not obj:
            return [], ""
        html = etree.HTML(obj.text)
        style_text = html.xpath("""//*[@id="player"]/script[1]/text()""")[0]
        for text in style_text.split("\n"):
            text = text.strip()
            if text:
                js_codes.append(text)
        param = self.FLASHVARS_PATTERN.search(js_codes[0]).group()
        return js_codes[:3], param[:-2]

    def parse_info(self, flashvars):
        download_url, download_quality = None, ""
        video_title = self.VIDEO_TITLE_PATTERN.search(flashvars)
        for quality, download_url_pattern in self.DOWNLOAD_URL_PATTERNS.items():
            download_url = download_url_pattern.search(flashvars)
            if not download_url:
                continue
            download_quality = quality
            break
        if not download_url:
            return [None, None, None]
        final_download_url = download_url.group(1)
        if video_title:
            video_title = f"{video_title.group(1)}.mp4"
        else:
            video_title = f"{uuid.uuid4().hex}.mp4"
        video_filename = f"{self.download_path}{os.sep}{make_valid_filename(video_title)}"
        return [final_download_url, download_quality, video_filename]

    # def search(self, keyword, op="relative", hd=False, start=0, end=20):
    #     query = {"search": keyword}
    #     if op != "relative" and op in ["mr", "mv", "tr", "lg"]:
    #         # mr: 最新, mv: 最多, tr: 评价最好, lg: 最长
    #         query["o"] = op
    #     if hd:  # 是否高清
    #         query["hd"] = 1
    #     r = self.get_html(SEARCH_URL, params=query)
    #     if r:
    #         html = etree.HTML(r.text)
    #         target_urls = html.xpath(r'//ul[@id="videoSearchResult"]//'
    #                                  r'div[@class="thumbnail-info-wrapper clearfix"]/span/a/@href')[start:end]
    #         return map(partial(urljoin, PH_URL), target_urls)
    #     return None
