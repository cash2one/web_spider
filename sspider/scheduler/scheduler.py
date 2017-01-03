#!/usr/bin/env python
# -*- encoding: utf-8 -*-



import itertools
import json
import logging
import os
import time
from collections import deque

from six import iteritems, itervalues
from six.moves import queue as Queue

import sys, os
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from libs import counter, utils
from .task_queue import TaskQueue

logger = logging.getLogger('scheduler')


class Project(object):
    '''
    project for scheduler
    '''
    def __init__(self, scheduler, project_info):
        '''
        '''
        self.scheduler = scheduler
        self.db_status = 'RUNNING'
        self.active_tasks = deque(maxlen=scheduler.ACTIVE_TASKS)
        self.task_queue = TaskQueue()

        self.md5sum = None

        self.update(project_info)
        self.task_loaded = False


    def update(self, project_info):
        self.project_info = project_info

        self.name = project_info['name']

        self.updatetime = project_info['updatetime']


        if self.active:
            self.task_queue.rate = project_info['rate']
            self.task_queue.burst = project_info['burst']
        else:
            self.task_queue.rate = 0
            self.task_queue.burst = 0

        logger.info('project %s updated, %d tasks',
                    self.name,  len(self.task_queue))

    @property
    def active(self):
        return self.db_status in ('RUNNING', 'DEBUG')
class Scheduler(object):
    UPDATE_PROJECT_INTERVAL = 5 * 60

    LOOP_LIMIT = 1000
    LOOP_INTERVAL = 0.1
    ACTIVE_TASKS = 100
    INQUEUE_LIMIT = 0
    EXCEPTION_LIMIT = 3
    DELETE_TIME = 24 * 60 * 60
    DEFAULT_RETRY_DELAY = {
        0: 30,
        1: 1*60*60,
        2: 6*60*60,
        3: 12*60*60,
        '': 24*60*60
    }
    FAIL_PAUSE_NUM = 10
    PAUSE_TIME = 5*60
    UNPAUSE_CHECK_NUM = 3

    TASK_PACK = 1
    STATUS_PACK = 2  # current not used
    REQUEST_PACK = 3  # current not used
    default_schedule = {
       'force_update': True,
        'priority': 0,
        'retries': 3,
        'exetime': 0,
        'age': -1,
        'itag': None,
    }
    def __init__(self, taskdb, projectdb, newtask_queue, status_queue,
                 out_queue, data_path='./data', resultdb=None):
        self.taskdb = taskdb
        self.projectdb = projectdb
        self.resultdb = resultdb
        self.newtask_queue = newtask_queue
        self.status_queue = status_queue
        self.out_queue = out_queue
        self.data_path = data_path

        self._send_buffer = deque()
        self._quit = False
        self._exceptions = 0
        self.projects = dict()
        self._force_update_project = True
        self._last_update_project = 0
        self._last_tick = int(time.time())
        self._postpone_request = []

        self._cnt = {
            "5m_time": counter.CounterManager(
                lambda: counter.TimebaseAverageEventCounter(30, 10)),
            "5m": counter.CounterManager(
                lambda: counter.TimebaseAverageWindowCounter(30, 10)),
            "1h": counter.CounterManager(
                lambda: counter.TimebaseAverageWindowCounter(60, 60)),
            "1d": counter.CounterManager(
                lambda: counter.TimebaseAverageWindowCounter(10 * 60, 24 * 6)),
            "all": counter.CounterManager(
                lambda: counter.TotalCounter()),
        }
        self._cnt['1h'].load(os.path.join(self.data_path, 'scheduler.1h'))
        self._cnt['1d'].load(os.path.join(self.data_path, 'scheduler.1d'))
        self._cnt['all'].load(os.path.join(self.data_path, 'scheduler.all'))
        self._last_dump_cnt = 0



    def _update_project_cnt(self, project_name):
        status_count = self.taskdb.status_count(project_name)
        self._cnt['all'].value(
            (project_name, 'success'),
            status_count.get(self.taskdb.SUCCESS, 0)
        )
        self._cnt['all'].value(
            (project_name, 'failed'),
            status_count.get(self.taskdb.FAILED, 0) + status_count.get(self.taskdb.BAD, 0)
        )
        self._cnt['all'].value(
            (project_name, 'pending'),
            status_count.get(self.taskdb.ACTIVE, 0)
        )

    def task_verify(self, task):
        '''
        return False if any of 'taskid', 'project', 'url' is not in task dict
                        or project in not in task_queue
        '''
        for each in ('taskid', 'project', 'url', ):
            if each not in task or not task[each]:
                logger.error('%s not in task: %.200r', each, task)
                return False
        if task['project'] not in self.projects:
            logger.error('unknown project: %s', task['project'])
            return False

        project = self.projects[task['project']]
        if not project.active:
            logger.error('project %s not started, please set status to RUNNING or DEBUG',
                         task['project'])
            return False
        return True

    def insert_task(self, task):
        '''insert task into database'''
        return self.taskdb.insert(task['project'], task['taskid'], task)

    def update_task(self, task):
        '''update task in database'''
        return self.taskdb.update(task['project'], task['taskid'], task)

    def put_task(self, task):
        '''put task to task queue'''
        _schedule = task.get('schedule', self.default_schedule)
        self.projects[task['project']].task_queue.put(task['taskid'])


    def send_task(self, task, force=True):
        '''
        dispatch task to fetcher

        out queue may have size limit to prevent block, a send_buffer is used
        '''
        try:
            self.out_queue.put_nowait(task)
        except Queue.Full:
            if force:
                self._send_buffer.appendleft(task)
            else:
                raise

    merge_task_fields = ['taskid', 'project', 'url', 'status', 'schedule', 'lastcrawltime']
    def _check_request(self):
        '''Check new task queue'''
        # check _postpone_request first


        tasks = {}
        while len(tasks) < self.LOOP_LIMIT:
            try:
                task = self.newtask_queue.get_nowait()
            except Queue.Empty:
                break

            if isinstance(task, list):
                _tasks = task
            else:
                _tasks = (task, )

            for task in _tasks:
                if not self.task_verify(task):
                    continue
                '''
                if task['taskid'] in self.projects[task['project']].task_queue:
                    if not task.get('schedule', {}).get('force_update', False):
                        logger.debug('ignore newtask %(project)s:%(taskid)s %(url)s', task)
                        continue
                '''
                if task['taskid'] in tasks:
                    if not task.get('schedule', {}).get('force_update', True):
                        continue

                tasks[task['taskid']] = task

        for task in itervalues(tasks):
            self.on_request(task)

        return len(tasks)



    request_task_fields = [
        'taskid',
        'project',
        'url',
        'status',
        'schedule',
        'fetch',
        'process',
        'track',
        'lastcrawltime'
    ]

    def _check_select(self):
        '''Select task to fetch & process'''


        taskids = []
        cnt = 0
        cnt_dict = dict()
        limit = self.LOOP_LIMIT
        for project in itervalues(self.projects):
            if cnt >= limit:
                break

            # task queue
            task_queue = project.task_queue
            task_queue.check_update()
            project_cnt = 0

            # check send_buffer here. when not empty, out_queue may blocked. Not sending tasks
            while cnt < limit and project_cnt < limit / 10:
                taskid = task_queue.get()
                if not taskid:
                    break

                taskids.append((project.name, taskid))
                cnt += 1

            cnt_dict[project.name] = project_cnt

        for project, taskid in taskids:
            self._load_put_task(project, taskid)

        return cnt_dict

    def _load_put_task(self, project, taskid):
        try:
            task = self.taskdb.get_task(project, taskid, fields=self.request_task_fields)
        except ValueError:
            logger.error('bad task pack %s:%s', project, taskid)
            return
        if not task:
            return
        task = self.on_select_task(task)

    def _print_counter_log(self):
        # print top 5 active counters
        keywords = ('pending', 'success', 'retry', 'failed')
        total_cnt = {}
        project_actives = []
        project_fails = []
        for key in keywords:
            total_cnt[key] = 0
        for project, subcounter in iteritems(self._cnt['5m']):
            actives = 0
            for key in keywords:
                cnt = subcounter.get(key, None)
                if cnt:
                    cnt = cnt.sum
                    total_cnt[key] += cnt
                    actives += cnt

            project_actives.append((actives, project))

            fails = subcounter.get('failed', None)
            if fails:
                project_fails.append((fails.sum, project))

        top_2_fails = sorted(project_fails, reverse=True)[:2]
        top_3_actives = sorted([x for x in project_actives if x[1] not in top_2_fails],
                               reverse=True)[:5 - len(top_2_fails)]

        log_str = ("in 5m: new:%(pending)d,success:%(success)d,"
                   "retry:%(retry)d,failed:%(failed)d" % total_cnt)
        for _, project in itertools.chain(top_3_actives, top_2_fails):
            subcounter = self._cnt['5m'][project].to_dict(get_value='sum')
            log_str += " %s:%d,%d,%d,%d" % (project,
                                            subcounter.get('pending', 0),
                                            subcounter.get('success', 0),
                                            subcounter.get('retry', 0),
                                            subcounter.get('failed', 0))
        logger.info(log_str)

    def _dump_cnt(self):
        '''Dump counters to file'''
        self._cnt['1h'].dump(os.path.join(self.data_path, 'scheduler.1h'))
        self._cnt['1d'].dump(os.path.join(self.data_path, 'scheduler.1d'))
        self._cnt['all'].dump(os.path.join(self.data_path, 'scheduler.all'))

    def _try_dump_cnt(self):
        '''Dump counters every 60 seconds'''
        now = time.time()
        if now - self._last_dump_cnt > 60:
            self._last_dump_cnt = now
            self._dump_cnt()
            self._print_counter_log()

    def _check_delete(self):
        '''Check project delete'''
        now = time.time()
        for project in list(itervalues(self.projects)):
            if project.db_status != 'STOP':
                continue
            if now - project.updatetime < self.DELETE_TIME:
                continue
            #if 'delete' not in self.projectdb.split_group(project.group):
            #    continue

            logger.warning("deleting project: %s!", project.name)
            del self.projects[project.name]
            self.taskdb.drop(project.name)
            self.projectdb.drop(project.name)
            if self.resultdb:
                self.resultdb.drop(project.name)
            for each in self._cnt.values():
                del each[project.name]

    def __len__(self):
        return sum(len(x.task_queue) for x in itervalues(self.projects))

    def quit(self):
        '''Set quit signal'''
        self._quit = True
        # stop xmlrpc server
        if hasattr(self, 'xmlrpc_server'):
            self.xmlrpc_ioloop.add_callback(self.xmlrpc_server.stop)
            self.xmlrpc_ioloop.add_callback(self.xmlrpc_ioloop.stop)

    def _delete_task_done(self):
        '''Check status queue'''
        cnt = 0
        try:
            while True:
                task = self.status_queue.get_nowait()
                # check _on_get_info result here
                self.on_task_status(task)
                cnt += 1
        except Queue.Empty:
            pass
        return cnt

    def _update_projects(self):
        '''Check project update'''
        now = time.time()
        if (
                    not self._force_update_project
                and self._last_update_project + self.UPDATE_PROJECT_INTERVAL > now
        ):
            return
        for project in self.projectdb.check_update(self._last_update_project):
            self._update_project(project)
            logger.debug("project: %s updated.", project['name'])
        self._force_update_project = False
        self._last_update_project = now

    scheduler_task_fields = ['taskid', 'project', 'schedule', ]

    def _load_tasks(self, project):
        '''load tasks from database'''
        task_queue = project.task_queue

        for task in self.taskdb.load_tasks(
                self.taskdb.ACTIVE, project.name, self.scheduler_task_fields
        ):
            taskid = task['taskid']
            _schedule = task.get('schedule', self.default_schedule)
            priority = _schedule.get('priority', self.default_schedule['priority'])
            exetime = _schedule.get('exetime', self.default_schedule['exetime'])
            task_queue.put(taskid, priority, exetime)
        project.task_loaded = True
        logger.debug('project: %s loaded %d tasks.', project.name, len(task_queue))

        if project not in self._cnt['all']:
            self._update_project_cnt(project)
        self._cnt['all'].value((project.name, 'pending'), len(project.task_queue))

    def _update_project(self, project):
        '''update one project'''
        if project['name'] not in self.projects:
            self.projects[project['name']] = Project(self, project)
        else:
            self.projects[project['name']].update(project)

        project = self.projects[project['name']]



        # load task queue when project is running and delete task_queue when project is stoped
        if project.active:
            if not project.task_loaded:
                self._load_tasks(project)
                project.task_loaded = True
        else:
            if project.task_loaded:
                project.task_queue = TaskQueue()
                project.task_loaded = False

            if project not in self._cnt['all']:
                self._update_project_cnt(project.name)
    def run_once(self):
        '''comsume queues and feed tasks to fetcher, once'''
        self._update_projects()#加载项目，任务队列
        self._delete_task_done()#检查状态队列，删除已完成任务
        self._check_request()#从new_task取一个任务分配给项目

        self._check_select()#从每个项目取一个任务发给fetcher
        self._check_delete()#删除stop项目
        self._try_dump_cnt()

    def run(self):
        '''Start scheduler loop'''
        logger.info("scheduler starting...")

        while not self._quit:
            try:
                time.sleep(self.LOOP_INTERVAL)
                self.run_once()
                self._exceptions = 0
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.exception(e)
                self._exceptions += 1
                if self._exceptions > self.EXCEPTION_LIMIT:
                    break
                continue

        logger.info("scheduler exiting...")
        self._dump_cnt()

    def trigger_on_start(self, project):
        '''trigger an on_start callback of project'''
        self.newtask_queue.put({
            "project": project,
            "taskid": "on_start",
            "url": "data:,on_start",
            "process": {
                "callback": "on_start",
            },
        })

    def xmlrpc_run(self, port=23333, bind='127.0.0.1', logRequests=False):
        '''Start xmlrpc interface'''
        from sspider.libs.wsgi_xmlrpc import WSGIXMLRPCApplication

        application = WSGIXMLRPCApplication()

        application.register_function(self.quit, '_quit')
        application.register_function(self.__len__, 'size')

        def start_project(projectname, url):
            if not self.projectdb.verify_project_name(projectname):
                return 'project name is not allowed!', 400

            project_info = self.projectdb.get(projectname, fields=['name', 'status', 'group'])


            if not project_info:
                info = {
                    'group': "",
                    'name': projectname,
                    'status': 'TODO',
                    'rate': 1,
                    'burst': 3,
                }
                self.projectdb.insert(projectname, info)
            self._force_update_project = True

            task = {
                "fetch":
                    {
                        "fetch_type":"phantomjs"
                    },
                "project": projectname,
                "taskid": "data:,on_start",
                "url": url
            }
            if self.task_verify(task):
                self.newtask_queue.put(task)

            return "ok",200

        application.register_function(start_project, 'startproject')
        def dump_counter(_time, _type):
            try:
                return self._cnt[_time].to_dict(_type)
            except:
                logger.exception('')
        application.register_function(dump_counter, 'counter')

        def new_task(task):
            if self.task_verify(task):
                self.newtask_queue.put(task)
                return True
            return False
        application.register_function(new_task, 'newtask')

        def send_task(task):
            '''dispatch task to fetcher'''
            self.send_task(task)
            return True
        application.register_function(send_task, 'send_task')

        def update_project():
            self._force_update_project = True
        application.register_function(update_project, 'update_project')

        def get_active_tasks(project=None, limit=100):
            allowed_keys = set((
                'type',
                'taskid',
                'project',
                'status',
                'url',
                'lastcrawltime',
                'updatetime',
                'track',
            ))
            track_allowed_keys = set((
                'ok',
                'time',
                'follows',
                'status_code',
            ))

            iters = [iter(x.active_tasks) for k, x in iteritems(self.projects)
                     if x and (k == project if project else True)]
            tasks = [next(x, None) for x in iters]
            result = []

            while len(result) < limit and tasks and not all(x is None for x in tasks):
                updatetime, task = t = max(t for t in tasks if t)
                i = tasks.index(t)
                tasks[i] = next(iters[i], None)
                for key in list(task):
                    if key == 'track':
                        for k in list(task[key].get('fetch', [])):
                            if k not in track_allowed_keys:
                                del task[key]['fetch'][k]
                        for k in list(task[key].get('process', [])):
                            if k not in track_allowed_keys:
                                del task[key]['process'][k]
                    if key in allowed_keys:
                        continue
                    del task[key]
                result.append(t)
            # fix for "<type 'exceptions.TypeError'>:dictionary key must be string"
            # have no idea why
            return json.loads(json.dumps(result))
        application.register_function(get_active_tasks, 'get_active_tasks')

        def get_projects_pause_status():
            result = {}
            for project_name, project in iteritems(self.projects):
                result[project_name] = project.paused
            return result
        application.register_function(get_projects_pause_status, 'get_projects_pause_status')

        def webui_update():
            return {
                'pause_status': get_projects_pause_status(),
                'counter': {
                    '5m_time': dump_counter('5m_time', 'avg'),
                    '5m': dump_counter('5m', 'sum'),
                    '1h': dump_counter('1h', 'sum'),
                    '1d': dump_counter('1d', 'sum'),
                    'all': dump_counter('all', 'sum'),
                },
            }
        application.register_function(webui_update, 'webui_update')

        import tornado.wsgi
        import tornado.ioloop
        import tornado.httpserver

        container = tornado.wsgi.WSGIContainer(application)
        self.xmlrpc_ioloop = tornado.ioloop.IOLoop()
        self.xmlrpc_server = tornado.httpserver.HTTPServer(container, io_loop=self.xmlrpc_ioloop)
        self.xmlrpc_server.listen(port=port, address=bind)
        logger.info('scheduler.xmlrpc listening on %s:%s', bind, port)
        self.xmlrpc_ioloop.start()

    def on_request(self, task):
        if self.INQUEUE_LIMIT and len(self.projects[task['project']].task_queue) >= self.INQUEUE_LIMIT:
            logger.debug('overflow task %(project)s:%(taskid)s %(url)s', task)
            return

        oldtask = self.taskdb.get_task(task['project'], task['taskid'],
                                       fields=self.merge_task_fields)
        if oldtask:
            return self.on_old_request(task, oldtask)
        else:
            return self.on_new_request(task)

    def on_new_request(self, task):
        '''Called when a new request is arrived'''
        task['status'] = self.taskdb.ACTIVE
        self.insert_task(task)
        self.put_task(task)

        project = task['project']
        self._cnt['5m'].event((project, 'pending'), +1)
        self._cnt['1h'].event((project, 'pending'), +1)
        self._cnt['1d'].event((project, 'pending'), +1)
        self._cnt['all'].event((project, 'pending'), +1)
        logger.info('new task %(project)s:%(taskid)s %(url)s', task)
        return task

    def on_old_request(self, task, old_task):
        '''Called when a crawled task is arrived'''
        now = time.time()

        _schedule = task.get('schedule', self.default_schedule)
        old_schedule = old_task.get('schedule', {})

        if _schedule.get('force_update') and self.projects[task['project']].task_queue.is_processing(task['taskid']):
            # when a task is in processing, the modify may conflict with the running task.
            # postpone the modify after task finished.
            logger.info('postpone modify task %(project)s:%(taskid)s %(url)s', task)
            self._postpone_request.append(task)
            return

        restart = False
        schedule_age = _schedule.get('age', self.default_schedule['age'])
        if _schedule.get('itag') and _schedule['itag'] != old_schedule.get('itag'):
            restart = True
        elif schedule_age >= 0 and schedule_age + (old_task.get('lastcrawltime', 0) or 0) < now:
            restart = True
        elif _schedule.get('force_update'):
            restart = True

        if not restart:
            logger.debug('ignore newtask %(project)s:%(taskid)s %(url)s', task)
            return

        if _schedule.get('cancel'):
            logger.info('cancel task %(project)s:%(taskid)s %(url)s', task)
            task['status'] = self.taskdb.BAD
            self.update_task(task)
            self.projects[task['project']].task_queue.delete(task['taskid'])
            return task

        task['status'] = self.taskdb.ACTIVE
        self.update_task(task)
        self.put_task(task)

        project = task['project']
        if old_task['status'] != self.taskdb.ACTIVE:
            self._cnt['5m'].event((project, 'pending'), +1)
            self._cnt['1h'].event((project, 'pending'), +1)
            self._cnt['1d'].event((project, 'pending'), +1)
        if old_task['status'] == self.taskdb.SUCCESS:
            self._cnt['all'].event((project, 'success'), -1).event((project, 'pending'), +1)
        elif old_task['status'] == self.taskdb.FAILED:
            self._cnt['all'].event((project, 'failed'), -1).event((project, 'pending'), +1)
        logger.info('restart task %(project)s:%(taskid)s %(url)s', task)
        return task

    def on_task_status(self, task):
        '''Called when a status pack is arrived'''
        try:
            procesok = task['track']['process']['ok']
            if not self.projects[task['project']].task_queue.done(task['taskid']):
                logging.error('not processing pack: %(project)s:%(taskid)s %(url)s', task)
                return None
        except KeyError as e:
            logger.error("Bad status pack: %s", e)
            return None

        if procesok:
            ret = self.on_task_done(task)
        else:
            ret = self.on_task_failed(task)

        if task['track']['fetch'].get('time'):
            self._cnt['5m_time'].event((task['project'], 'fetch_time'),
                                       task['track']['fetch']['time'])
        if task['track']['process'].get('time'):
            self._cnt['5m_time'].event((task['project'], 'process_time'),
                                       task['track']['process'].get('time'))
        self.projects[task['project']].active_tasks.appendleft((time.time(), task))
        return ret

    def on_task_done(self, task):
        '''Called when a task is done and success, called by `on_task_status`'''
        task['status'] = self.taskdb.SUCCESS
        task['lastcrawltime'] = time.time()

        if 'schedule' in task:
            if task['schedule'].get('auto_recrawl') and 'age' in task['schedule']:
                task['status'] = self.taskdb.ACTIVE
                next_exetime = task['schedule'].get('age')
                task['schedule']['exetime'] = time.time() + next_exetime
                self.put_task(task)
            else:
                del task['schedule']
        self.update_task(task)

        project = task['project']
        self._cnt['5m'].event((project, 'success'), +1)
        self._cnt['1h'].event((project, 'success'), +1)
        self._cnt['1d'].event((project, 'success'), +1)
        self._cnt['all'].event((project, 'success'), +1).event((project, 'pending'), -1)
        logger.info('task done %(project)s:%(taskid)s %(url)s', task)
        return task

    def on_task_failed(self, task):
        '''Called when a task is failed, called by `on_task_status`'''

        if 'schedule' not in task:
            old_task = self.taskdb.get_task(task['project'], task['taskid'], fields=['schedule'])
            if old_task is None:
                logging.error('unknown status pack: %s' % task)
                return
            task['schedule'] = old_task.get('schedule', {})

        retries = task['schedule'].get('retries', self.default_schedule['retries'])
        retried = task['schedule'].get('retried', 0)

        project_info = self.projects[task['project']]
        retry_delay = project_info.retry_delay or self.DEFAULT_RETRY_DELAY
        next_exetime = retry_delay.get(retried, retry_delay.get('', self.DEFAULT_RETRY_DELAY['']))

        if task['schedule'].get('auto_recrawl') and 'age' in task['schedule']:
            next_exetime = min(next_exetime, task['schedule'].get('age'))
        else:
            if retried >= retries:
                next_exetime = -1
            elif 'age' in task['schedule'] and next_exetime > task['schedule'].get('age'):
                next_exetime = task['schedule'].get('age')

        if next_exetime < 0:
            task['status'] = self.taskdb.FAILED
            task['lastcrawltime'] = time.time()
            self.update_task(task)

            project = task['project']
            self._cnt['5m'].event((project, 'failed'), +1)
            self._cnt['1h'].event((project, 'failed'), +1)
            self._cnt['1d'].event((project, 'failed'), +1)
            self._cnt['all'].event((project, 'failed'), +1).event((project, 'pending'), -1)
            logger.info('task failed %(project)s:%(taskid)s %(url)s' % task)
            return task
        else:
            task['schedule']['retried'] = retried + 1
            task['schedule']['exetime'] = time.time() + next_exetime
            task['lastcrawltime'] = time.time()
            self.update_task(task)
            self.put_task(task)

            project = task['project']
            self._cnt['5m'].event((project, 'retry'), +1)
            self._cnt['1h'].event((project, 'retry'), +1)
            self._cnt['1d'].event((project, 'retry'), +1)
            # self._cnt['all'].event((project, 'retry'), +1)
            logger.info('task retry %d/%d %%(project)s:%%(taskid)s %%(url)s' % (
                retried, retries), task)
            return task

    def on_select_task(self, task):
        '''Called when a task is selected to fetch & process'''
        # inject informations about project
        logger.info('select %(project)s:%(taskid)s %(url)s', task)

        project_info = self.projects.get(task['project'])
        assert project_info, 'no such project'
        task['type'] = self.TASK_PACK
        #task['group'] = project_info.group
        task['project_md5sum'] = project_info.md5sum
        task['project_updatetime'] = project_info.updatetime

        # lazy join project.crawl_config
        if getattr(project_info, 'crawl_config', None):
            task = BaseHandler.task_join_crawl_config(task, project_info.crawl_config)

        project_info.active_tasks.appendleft((time.time(), task))
        self.send_task(task)
        return task

