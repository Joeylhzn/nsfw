# -*- coding: utf-8 -*-
import os
import re

import js2py

from lxml import etree

from utils import BaseSpider
from config import DOWNLOAD_DIR


DOWNLOAD_PATH = DOWNLOAD_DIR + os.sep + "91porn"
STRENCODE = re.compile(r"<!--\s+document.write\((.*)\).*")
SOURCE = re.compile(r".*=\'(.*)\' type=\'video/mp4\'")


class Spider(BaseSpider):

    def init(self):
        if not os.path.exists(DOWNLOAD_PATH):
            os.mkdir(DOWNLOAD_PATH)
        r = self.get_html("http://www.91porn.com/js/md5.js")
        self.md5 = r.text
        self.context = js2py.EvalJs()

    def run(self, url):
        r = self.get_html(url)
        if not r:
            return None
        html = etree.HTML(r.content)
        script = html.xpath(r"""//*[@id="player_one"]/script/text()""")[0].strip()
        js_code = STRENCODE.match(script).group(1)
        js_code = f"{self.md5}console.log({js_code});"
        eval_value = self.context.eval(js_code)
        source_code = SOURCE.match(eval_value)
