#!/usr/bin/env python
# -*- encoding: utf-8 -*-

import time
import json
import logging
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

    def on_result(self, result):
        '''Called every result'''
        if not result:
            return
        if 'taskid' in result and 'project' in result and 'url' in result:
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
                if isinstance(result, dict) and result.get('finish'):
                    self.resultdb.finish(result['finish'])
                    continue
                for item in result:
                    self.on_result(item)

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
