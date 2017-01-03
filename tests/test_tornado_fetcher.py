#!/usr/bin/env python
# -*- encoding: utf-8 -*-
#抓取模块的测试用例
#主要测能否抓取js,ajax,表格。
#
#

import os,sys
import json
import copy
import time
import subprocess
import unittest2 as unittest

import logging.config
import httpbin  #用于测试的web服务器
import data_webpage

logging.config.fileConfig("../conf/logging.conf")

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

import xmlrpclib as xmlrpc_client
from sspider.libs import utils
from sspider.libs.multiprocessing_queue import Queue
from sspider.libs.response import rebuild_response
from sspider.fetcher.tornado_fetcher import Fetcher


class TestFetcher(unittest.TestCase):
    sample_task_http = {
        'taskid': 'taskid',
        'project': 'project',
        'url': '',
        'fetch': {
            'method': 'GET',
            'headers': {
                'Cookie': 'a=b',
                'a': 'b'
            },
            'cookies': {
                'c': 'd',
            },
            'timeout': 60,
            'save': 'abc',
        },
        'process': {
            'callback': 'callback',
            'save': [1, 2, 3],
        },
    }

    @classmethod
    def setUpClass(self):
        self.httpbin_thread = utils.run_in_subprocess(httpbin.app.run, port=14887, passthrough_errors=False)
        self.httpbin = 'http://127.0.0.1:14887'

        self.inqueue = Queue(10)
        self.outqueue = Queue(10)
        self.fetcher = Fetcher(self.inqueue, self.outqueue)
        self.fetcher.phantomjs_proxy = '127.0.0.1:25555'

        self.thread = utils.run_in_thread(self.fetcher.run)

        try:
            self.phantomjs = subprocess.Popen(['phantomjs',
                                               os.path.join(ROOT_DIR,
<<<<<<< HEAD
                                                            'sspider/fetcher/phantomjs/phantomjs_server.js'),
=======
                                                            'sspider/fetcher/phantomjs_fetcher.js'),
>>>>>>> 4f6bd53db96ef6b346bf2e3bb76b9a01e6ada01e
                                               '25555'])
        except OSError, e:
            print e
            self.phantomjs = None
        time.sleep(2)

    @classmethod
    def tearDownClass(self):
        self.httpbin_thread.terminate()
        self.httpbin_thread.join()

        if self.phantomjs:
            self.phantomjs.kill()
            self.phantomjs.wait()

        self.fetcher.quit()
        self.thread.join()
        assert not utils.check_port_open(5000)
        assert not utils.check_port_open(23333)
        assert not utils.check_port_open(24444)
        assert not utils.check_port_open(25555)
        assert not utils.check_port_open(14887)

    def test_phantomjs_js(self):
        if not self.phantomjs:
            raise unittest.SkipTest('no phantomjs')
        request = copy.deepcopy(self.sample_task_http)
        request['url'] = self.httpbin+'/js'
        request['fetch']['fetch_type'] = 'phantomjs'
        request['fetch']['headers']['User-Agent'] = 'webspider-test'
        result = self.fetcher.sync_fetch(request)
        print result
        self.assertEqual(result['status_code'], 200)
        self.assertIn(r'js_link1.php?id=1&amp;msg=abc', result['content'])
        self.assertIn(u'js_link2.php?id=2', result['content'])

    '''
    def test_phantomjs_form(self):
        if not self.phantomjs:
            raise unittest.SkipTest('no phantomjs')
        request = copy.deepcopy(self.sample_task_http)
        request['url'] = self.httpbin+'/form'
        request['fetch']['fetch_type'] = 'phantomjs'
        request['fetch']['headers']['User-Agent'] = 'webspider-test'
        result = self.fetcher.sync_fetch(request)
        print result
    '''

    def test_http_get(self):
        request = copy.deepcopy(self.sample_task_http)
        request['url'] = self.httpbin + '/get'
        result = self.fetcher.sync_fetch(request)
        #print result
        response = rebuild_response(result)

        self.assertEqual(response.status_code, 200, result)#assertEqual(first, second, msg=None)
        self.assertEqual(response.orig_url, request['url'])
        self.assertEqual(response.save, request['fetch']['save'])
        self.assertIsNotNone(response.json, response.content)
        self.assertEqual(response.json['headers'].get('A'), 'b', response.json)
        self.assertIn('c=d', response.json['headers'].get('Cookie'), response.json)
        self.assertIn('a=b', response.json['headers'].get('Cookie'), response.json)



if __name__ == "__main__":
    unittest.main()
