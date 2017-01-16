#!/usr/bin/env python
# -*- encoding: utf-8 -*-


import sys
import six
import time
import logging
import traceback
logger = logging.getLogger("processor")

from six.moves import queue as Queue

import os
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from libs.url import (
    quote_chinese, _build_url, _encode_params,
    _encode_multipart_formdata, curl_to_arguments)
from libs import utils
from libs.log import LogFormatter
from libs.utils import pretty_unicode, hide_me
from libs.response import rebuild_response
from libs.utils import md5string, timeout, get_domain_from_url
from project_module import ProjectManager, ProjectFinder


class ProcessorResult(object):
    """The result and logs producted by a callback"""

    def __init__(self, result=None, follows=(), messages=(),
                 logs=(), exception=None, extinfo={}, save=None):
        self.result = result
        self.follows = follows
        self.messages = messages
        self.logs = logs
        self.exception = exception
        self.extinfo = extinfo
        self.save = save

    def rethrow(self):
        """rethrow the exception"""

        if self.exception:
            raise self.exception

    def logstr(self):
        """handler the log records to formatted string"""

        result = []
        formater = LogFormatter(color=False)
        for record in self.logs:
            if isinstance(record, six.string_types):
                result.append(pretty_unicode(record))
            else:
                if record.exc_info:
                    a, b, tb = record.exc_info
                    tb = hide_me(tb, globals())
                    record.exc_info = a, b, tb
                result.append(pretty_unicode(formater.format(record)))
                result.append(u'\n')
        return u''.join(result)


class Processor(object):
    PROCESS_TIME_LIMIT = 30
    EXCEPTION_LIMIT = 3

    RESULT_LOGS_LIMIT = 1000
    RESULT_RESULT_LIMIT = 10

    def __init__(self, projectdb, inqueue, status_queue, newtask_queue, result_queue,
                 enable_stdout_capture=True,
                 enable_projects_import=True,
                 process_time_limit=PROCESS_TIME_LIMIT):
        self.inqueue = inqueue
        self.status_queue = status_queue
        self.newtask_queue = newtask_queue
        self.result_queue = result_queue
        self.projectdb = projectdb
        self.enable_stdout_capture = enable_stdout_capture

        self._quit = False
        self._exceptions = 10
        self.project_manager = ProjectManager(projectdb, dict(
            result_queue=self.result_queue,
            enable_stdout_capture=self.enable_stdout_capture,
            process_time_limit=process_time_limit,
        ))

        if enable_projects_import:
            self.enable_projects_import()

    def enable_projects_import(self):
        '''
        Enable import other project as module

        `from project import project_name`
        '''
        if six.PY2:
            sys.meta_path.append(ProjectFinder(self.projectdb))

    def __del__(self):
        pass

    schedule_fields = ('priority', 'retries', 'exetime', 'age', 'itag', 'force_update', 'auto_recrawl', 'cancel')
    fetch_fields = ('method', 'headers', 'data', 'connect_timeout', 'timeout', 'allow_redirects', 'cookies',
                    'proxy', 'etag', 'last_modifed', 'last_modified', 'save', 'js_run_at', 'js_script',
                    'js_viewport_width', 'js_viewport_height', 'load_images', 'fetch_type', 'use_gzip', 'validate_cert',
                    'max_redirects', 'robots_txt')
    process_fields = ('callback', 'process_time_limit')

    def _get_follows(self, task, content):
        tasks = []
        try:
            project = task['project']
            if not isinstance(content, dict):
                return []
            if not content.has_key("response"):
                return []
            if not content["response"].has_key("details"):
                return []
            # 提取ajax
            if content["response"]["details"].has_key('ajax'):
                ajax = content["response"]["details"]["ajax"]
                for item in ajax:
                    # 只爬取设定的网站
                    if get_domain_from_url(task["url"]) != get_domain_from_url(item["url"]):
                        continue

                    # print item["url"]
                    newtask = {}
                    newtask['schedule'] = {'force_update': True}

                    fetch = {u'fetch_type': u'phantomjs'}
                    fetch["method"] = item["method"]
                    fetch["data"] = item["data"]
                    newtask["seed_url"] = task["url"]
                    newtask['fetch'] = fetch
                    newtask['process'] = {}
                    newtask['project'] = project
                    newtask['url'] = item["url"]
                    newtask['taskid'] = self.get_taskid(newtask)
                    tasks.append(newtask)
            # 提取表单
            if content["response"]["details"].has_key("forms"):
                forms = content["response"]["details"]["forms"]
                for item in forms:
                    # 只爬取设定的网站
                    if get_domain_from_url(task["url"]) != get_domain_from_url(item["url"]):
                        continue

                    # print item["url"]
                    newtask = {}
                    newtask['schedule'] = {'force_update': True}
                    newtask["seed_url"] = task["url"]
                    fetch = {u'fetch_type': u'phantomjs'}
                    fetch["method"] = item["method"]
                    fetch["data"] = item["data"]

                    newtask['fetch'] = fetch
                    newtask['process'] = {}
                    newtask['project'] = project
                    newtask['url'] = item["url"]
                    newtask['taskid'] = self.get_taskid(newtask)
                    tasks.append(newtask)
            # 提取链接
            for item in content["response"]["details"]["links"]:
                # 只爬取设定的网站
                if get_domain_from_url(task["url"]) != get_domain_from_url(item["url"]):
                    continue
                newtask = {}
                newtask["seed_url"] = task["url"]
                url = item["url"]
                # print url
                #url = quote_chinese(_build_url(url.strip()))

                newtask['schedule'] = {'force_update': True}
                fetch = {u'fetch_type': u'phantomjs'}
                newtask['fetch'] = fetch

                process = {}
                newtask['process'] = process
                newtask['project'] = project
                newtask['url'] = url
                newtask['taskid'] = self.get_taskid(newtask)

                tasks.append(newtask)
        except Exception, e:
            print e
        return tasks

    def get_taskid(self, task):
        '''Generate taskid by information of task md5(url) by default, override me'''
        return md5string(task['url'])
    def on_task(self, task, response):
        '''Deal one task'''
        start_time = time.time()
        response = rebuild_response(response)

        try:
            assert 'taskid' in task, 'need taskid in task'
            project = task['project']
            updatetime = task.get('project_updatetime', None)
            md5sum = task.get('project_md5sum', None)
            project_data = self.project_manager.get(project, updatetime, md5sum)
            assert project_data, "no such project!"
        except Exception as e:
            logstr = traceback.format_exc()
            ret = ProcessorResult(logs=(logstr, ), exception=e)
        process_time = time.time() - start_time
        ret = ProcessorResult()
        ret.follows = self._get_follows(task, response.content)

        if not ret.extinfo.get('not_send_status', False):
            status_pack = {
                'taskid': task['taskid'],
                'project': task['project'],
                'url': task.get('url'),
                'track': {
                    'fetch': {
                        'ok': response.isok(),
                        'redirect_url': response.url if response.url != response.orig_url else None,
                        'time': response.time,
                        'error': response.error,
                        'status_code': response.status_code,
                        'encoding': getattr(response, '_encoding', None),
                        'headers': "",
                        'content': "",
                    },
                    'process': {
                        'ok': not ret.exception,
                        'time': process_time,
                        'follows': len(ret.follows),
                        'result': (
                            None if ret.result is None
                            else utils.text(ret.result)[:self.RESULT_RESULT_LIMIT]
                        ),
                        'logs': "",
                        'exception': ret.exception,
                    },
                    'save': "",
                },
            }
            if 'schedule' in task:
                status_pack['schedule'] = task['schedule']

            # FIXME: unicode_obj should used in scheduler before store to database
            # it's used here for performance.
            self.status_queue.put(utils.unicode_obj(status_pack))

        # FIXME: unicode_obj should used in scheduler before store to database
        # it's used here for performance.
        if ret.follows:
            #一次发1000个任务，以免频繁发送任务
            for each in (ret.follows[x:x + 1000] for x in range(0, len(ret.follows), 1000)):
                self.newtask_queue.put([utils.unicode_obj(newtask) for newtask in each])
                self.result_queue.put([utils.unicode_obj(newtask) for newtask in each])


        return True

    def quit(self):
        '''Set quit signal'''
        self._quit = True

    def run(self):
        '''Run loop'''
        logger.info("processor starting...")

        while not self._quit:
            try:
                task, response = self.inqueue.get(timeout=1)
                self.on_task(task, response)
                self._exceptions = 0
            except Queue.Empty as e:
                continue
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.exception(e)
                self._exceptions += 1
                if self._exceptions > self.EXCEPTION_LIMIT:
                    break
                continue

        logger.info("processor exiting...")
