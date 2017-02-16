#!/usr/bin/env python
# -*- coding: utf-8 -*-

__title__ = ""
__author__ = "jx"
__mtime__ = "16-12-9"
import sys, time


import traceback

import xmlrpclib as xmlrpc_client




rpc = xmlrpc_client.ServerProxy("http://127.0.0.1:23333/", allow_none=True)
# print rpc.StartProject("test", "http://127.0.0.1:18888/html_link")#/pyspider/test.html")"http://www.freebuf.com")#"pyspider/test.html"
# print rpc.StartProject("tet", "http://www.freebuf.com")
# print rpc.StartProject("ee", "http://www.cowinbio.com/")
print rpc.StartProject("test2", "http://demo.aisec.cn/demo/aisec/")
# time.sleep(15)
# print rpc.DropProject("test")
# print rpc.StopProject("ee")
