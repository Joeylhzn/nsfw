# -*- coding: utf-8 -*-
import os
import re

from urllib.parse import urljoin

from lxml import etree

from .base import M3U8Spider, make_valid_filename


class Spider(M3U8Spider):

    name = "xvideos"

    VIDEOHLS = re.compile(r".*setVideoHLS\(\'(.*?)\'\).*", re.DOTALL)
    VIDEOURLHIGH = re.compile(r".*setVideoUrlHigh\(\'(.*?)\'\).*", re.DOTALL)
    VIDEOURLLOW = re.compile(r".*setVideoUrlLow\(\'(.*?)\'\).*", re.DOTALL)

    M3U8 = re.compile(r"(^hls-(\d{3,4}p).*?$)", re.MULTILINE)

    def get_m3u8(self, url):
        qualities = ["1080p", "720p", "480p", "360p", "250p"]
        r = self.get_html(url)
        if not r:
            return None, None
        m3u8_dct = {item[1]: item[0] for item in self.M3U8.findall(r.text)}
        for quality in qualities:
            if quality in m3u8_dct:
                return urljoin(url, m3u8_dct[quality]), quality
        return None, None

    def run(self, url):
        r = self.get_html(url)
        if not r:
            return None
        html = etree.HTML(r.content)
        title = url.rpartition("/")[-1]
        filename = self.download_path + os.sep + make_valid_filename(title)
        script = self.xpath(html,
                            r'//div[@id="video-player-bg"]/script[4]/text()')
        if not script:
            return None
        hls = self.VIDEOHLS.match(script)
        if hls:
            m3u8, quality = self.get_m3u8(hls.group(1))
            if m3u8:
                self.log(
                    f"got video url {m3u8},"
                    f"\nquality is {quality},"
                    f"\ndownload path is {filename}"
                )
                self.filename = filename
                self.download(m3u8)
        else:
            video = self.VIDEOURLHIGH.match(script) \
                    or self.VIDEOURLLOW.match(script)
            if not video:
                return None
            else:
                video_url = video.group(1)
            self.log(
                f"got video url {video_url},\ndownload path is {filename}"
            )
            super(M3U8Spider, self).download(
                video_url, filename, url, max_workers=10
            )
