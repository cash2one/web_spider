#!/usr/bin/env python
# -*- encoding: utf-8 -*-

import os,sys

import httpbin  #用于测试的web服务器
import data_webpage

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)


from sspider.libs import utils

import time

if __name__ == "__main__":
    utils.run_in_subprocess(httpbin.app.run, port=18888, passthrough_errors=False)

    time.sleep(9999999999)
