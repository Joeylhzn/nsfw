# -*- coding: utf-8 -*-
import os
import re
import uuid

import js2py

from lxml import etree

from utils import BaseSpider, make_valid_filename
from config import DOWNLOAD_DIR


DOWNLOAD_PATH = DOWNLOAD_DIR + os.sep + "91porn"
STRENCODE = re.compile(r"<!--\s*document.write\(strencode\((.*)\)\).*")
SOURCE = re.compile(r".*src=\'(.*)\' type=\'video/mp4\'")


class Spider(BaseSpider):

    def init(self):
        if not os.path.exists(DOWNLOAD_PATH):
            os.mkdir(DOWNLOAD_PATH)
        r = self.get_html("http://www.91porn.com/js/md5.js")
        self.context = js2py.EvalJs()
        self.context.execute(r.text)

    def run(self, url):
        r = self.get_html(url)
        if not r:
            return None
        html = etree.HTML(r.content)
        title = html.xpath(r"""/html/head/title/text()""")[0].strip().replace('\n', '').replace('\t', '')
        filename = DOWNLOAD_PATH + os.sep + make_valid_filename(f"{title}.mp4")
        script = html.xpath(r"""//*[@id="player_one"]/script/text()""")[0].strip()
        js_code = STRENCODE.match(script).group(1)
        params = list(map(lambda x: x[1: -1], js_code.split(",")))
        eval_value = self.context.strencode(*params)
        video_url = SOURCE.match(eval_value).group(1)
        self.log(f"got video url {video_url},\ndownload path is {filename}")
        self.download(video_url, filename, url)
