# -*- coding: utf-8 -*-
import os
import re

from lxml import etree

from utils import BaseSpider, make_valid_filename
from config import DOWNLOAD_DIR


DOWNLOAD_PATH = DOWNLOAD_DIR + os.sep + "xvideos"
VIDEOURLHIGH = re.compile(r".*setVideoUrlHigh\(\'(.*?)\'\).*", re.DOTALL)
VIDEOURLLOW = re.compile(r".*setVideoUrlLow\(\'(.*?)\'\).*", re.DOTALL)


class Spider(BaseSpider):

    def init(self):
        if not os.path.exists(DOWNLOAD_PATH):
            os.mkdir(DOWNLOAD_PATH)

    def run(self, url):
        r = self.get_html(url)
        if not r:
            return None
        html = etree.HTML(r.content)
        title = url.rpartition("/")[-1]+".mp4"
        filename = DOWNLOAD_PATH + os.sep + make_valid_filename(title)
        script = html.xpath(r"""//div[@id="video-player-bg"]/script[4]/text()""")[0]
        high = VIDEOURLHIGH.match(script)
        if not high:
            low = VIDEOURLLOW.match(script)
            if not low:
                return None
            video_url = low.group(1)
            quality = "low"
        else:
            video_url = high.group(1)
            quality = "high"
        self.log(f"got video url {video_url},\nquality is {quality},\ndownload path is {filename}")
        self.download(video_url, filename, url, max_worker=10)



