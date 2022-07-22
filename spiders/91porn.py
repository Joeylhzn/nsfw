import os
import re
import logging

import js2py

from lxml import etree

from .base import M3U8Spider, make_valid_filename


class Spider(M3U8Spider):

    name = "91porn"

    STRENCODE = re.compile(r"<!--\s*document.write\(strencode2\((.*)\)\).*")
    SOURCE = re.compile(r".*src=\'(.*)\' type=\'.*\'")

    def init(self):
        r = self.get_html("http://www.91porn.com/js/m2.js")
        self.context = js2py.EvalJs()
        self.context.execute(r.text)
        super(Spider, self).init()

    def run(self, url):
        r = self.get_html(url)
        if not r:
            self.log(f"can not get {url}", logging.ERROR)
            return None
        html = etree.HTML(r.content)
        target = self.xpath(html, r'//*[@class="login_register_header"]/text()')
        if not target:
            return None
        title = target.strip().replace('\n', '').replace('\t', '')
        self.filename = make_valid_filename(self.download_path, title)
        script = self.xpath(html, r'//*[@id="player_one"]/script/text()')
        if not script:
            self.log(f"{self.name} 达到访问上限", logging.ERROR)
            return None
        js_code = self.STRENCODE.match(script.strip()).group(1)
        params = list(map(lambda x: x[1: -1], js_code.split(",")))
        eval_value = self.context.strencode2(*params)
        video_url = self.SOURCE.match(eval_value).group(1)
        self.log(f"got video url {video_url},\ndownload path is {self.filename}")
        self.download(video_url)
