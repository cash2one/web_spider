#!/usr/bin/env python
# -*- coding: utf-8 -*-

__title__ = ""
__author__ = "jx"
__mtime__ = "16-12-7"

__version__ = "0.1"
__prog_name__ = "webspider"

import os

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..",".."))

CACHE_DIR = os.path.join(ROOT_DIR, "cache")
CONF_DIR = os.path.join(ROOT_DIR, "conf")
DATA_DIR = os.path.join(ROOT_DIR, "data")
LOG_DIR = os.path.join(ROOT_DIR, "log")

def test():
    print ROOT_DIR
    print CONF_DIR
    print CACHE_DIR
    print LOG_DIR

if __name__ == "__main__":
    test()