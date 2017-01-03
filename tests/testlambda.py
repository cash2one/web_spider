#!/usr/bin/env python
# -*- coding: utf-8 -*-

__title__ = ""
__author__ = "jx"
__mtime__ = "16-12-9"
import sys


import traceback

import xmlrpclib as xmlrpc_client




rpc = xmlrpc_client.ServerProxy("http://127.0.0.1:23333/", allow_none=True)
print rpc.startproject("test", "http://www.freebuf.com/")#""http://demo.aisec.cn/demo/aisec/")