#!/usr/bin/env python
# -*- encoding: utf-8 -*-

import os
import re
import time
import json
import logging
import urlparse
from six.moves import queue as Queue
logger = logging.getLogger("result")


class ResultWorker(object):

    """
    do with result
    override this if needed.
    """

    def __init__(self, resultdb, inqueue):
        self.resultdb = resultdb
        self.inqueue = inqueue
        self._quit = False

    def _url_match(self, url):
        filter_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../conf/url_filter.conf'))
        with open(filter_path, 'r') as f:
            suffix = f.read().replace('\n', '|')
        pattern = '^\.(' + suffix + ')$'
        text = os.path.splitext(urlparse.urlparse(url).path)
        return not re.match(pattern, text[1])

    def on_result(self, result):
        '''Called every result'''
        if not result:
            return
        if 'taskid' in result and 'project' in result and 'url' in result:
            if self._url_match(result['url']):
                logger.info('result %s:%s %s -> %.30r' % (
                    result['project'], result['taskid'], result['url'], result))
                data_str = result['fetch'].get('data', '')
                data_dict = {}

                if data_str:
                    for i in data_str.split('&'):
                        data_dict[i.split('=')[0]] = i.split('=')[1]

                obj = {
                    'url': result['url'],
                    'type': result['fetch'].get('method', 'link'),
                    'param': {
                        'data': data_dict
                    },
                    'seed_url': result['seed_url']
                }
                return self.resultdb.save(project=result['project'], result=obj)
        else:
            logger.warning('result UNKNOW -> %.30r' % result)
            return

    def quit(self):
        self._quit = True

    def run(self):
        '''Run loop'''
        logger.info("result_worker starting...")

        while not self._quit:
            try:
                result = self.inqueue.get(timeout=1)
                self.on_result(result)

            except Queue.Empty as e:
                continue
            except KeyboardInterrupt:
                break
            except AssertionError as e:
                logger.error(e)
                continue
            except Exception as e:
                logger.exception(e)
                continue

        logger.info("result_worker exiting...")


class OneResultWorker(ResultWorker):
    '''Result Worker for one mode, write results to stdout'''

    def on_result(self, result):
        '''Called every result'''
        if not result:
            return
        if 'taskid' in result and 'project' in result and 'url' in result:
            logger.info('result %s:%s %s -> %.30r' % (
                result['project'], result['taskid'], result['url'], result))
            print(json.dumps({
                'taskid': result['taskid'],
                'project': result['project'],
                'url': result['url'],
                'result': result,
                'updatetime': time.time()
            }))
        else:
            logger.warning('result UNKNOW -> %.30r' % result)
            return
