#!/usr/bin/env python
# -*- coding: utf-8 -*-

__title__ = ""
__author__ = "jx"
__mtime__ = "16-12-11"

import os,sys
from bs4 import BeautifulSoup
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(ROOT_DIR)

from sspider.fetcher.tornado_fetcher_test import Fetcher

def test():
  fetcher=Fetcher(
  user_agent='phantomjs', # user agent
  phantomjs_proxy='http://localhost:25555', # phantomjs url
  pool_size=10, # max httpclient num
  async=False
  )

<<<<<<< HEAD
  html_doc = fetcher.phantomjs_fetch("http://www.baidu.com")
=======
  html_doc = fetcher.phantomjs_fetch("http://demo.aisec.cn/demo/aisec/")
>>>>>>> 4f6bd53db96ef6b346bf2e3bb76b9a01e6ada01e

  soup = BeautifulSoup(html_doc["content"], "lxml")


  a = soup.find_all('a')
  for u in a:
    print u.get("href")

if __name__ == "__main__":
  test()