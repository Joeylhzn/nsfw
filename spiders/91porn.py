import os
import re
import logging

import js2py

from lxml import etree

from .base import BaseSpider, make_valid_filename


class Spider(BaseSpider):

    name = "91porn"

    STRENCODE = re.compile(r"<!--\s*document.write\(strencode\((.*)\)\).*")
    SOURCE = re.compile(r".*src=\'(.*)\' type=\'video/mp4\'")

    def init(self):
        r = self.get_html("http://www.91porn.com/js/md5.js")
        self.context = js2py.EvalJs()
        self.context.execute(r.text)
        super(Spider, self).init()

    def run(self, url):
        r = self.get_html(url)
        if not r:
            return None
        html = etree.HTML(r.content)
        title = html.xpath(r"""/html/head/title/text()""")[0].strip().replace('\n', '').replace('\t', '')
        filename = self.download_path + os.sep + make_valid_filename(title)
        try:
            script = html.xpath(r"""//*[@id="player_one"]/script/text()""")[0].strip()
        except KeyError:
            self.log(f"{self.name} 达到访问上限", logging.ERROR)
            return None
        js_code = self.STRENCODE.match(script).group(1)
        params = list(map(lambda x: x[1: -1], js_code.split(",")))
        eval_value = self.context.strencode(*params)
        video_url = self.SOURCE.match(eval_value).group(1)
        self.log(f"got video url {video_url},\ndownload path is {filename}")
        self.download(video_url, filename, url)
