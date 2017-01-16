#!/usr/bin/env python
# -*- encoding: utf-8 -*-


import re
import time
import json

import sys,os
DATABASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if DATABASE_DIR not in sys.path:
    sys.path.append(DATABASE_DIR)

from sqlitebase import SQLiteMixin, SplitTableMixin
from sspider.database.base.taskdb import TaskDB as BaseTaskDB
from sspider.database.basedb import BaseDB


class TaskDB(SQLiteMixin, SplitTableMixin, BaseTaskDB, BaseDB):
    __tablename__ = 'taskdb'
    placeholder = '?'

    def __init__(self, path):
        self.path = path
        self.last_pid = 0
        self.conn = None
        self._list_project()

    def _create_project(self, project):
        assert re.match(r'^\w+$', project) is not None
        tablename = self._tablename(project)
        self._execute('''CREATE TABLE IF NOT EXISTS `%s` (
                taskid PRIMARY KEY,
                project,
                url, status,
                seed_url,
                schedule, fetch, process, track,
                lastcrawltime, updatetime
                )''' % tablename)
        self._execute(
            '''CREATE INDEX `status_%s_index` ON %s (status)'''
            % (tablename, self.escape(tablename))
        )

    def _parse(self, data):
        for each in ('schedule', 'fetch', 'process', 'track'):
            if each in data:
                if data[each]:
                    data[each] = json.loads(data[each])
                else:
                    data[each] = {}
        return data

    def _stringify(self, data):
        for each in ('schedule', 'fetch', 'process', 'track'):
            if each in data:
                data[each] = json.dumps(data[each])
        return data

    def load_tasks(self, status, project=None, fields=None):
        if project and project not in self.projects:
            return
        where = "status = %d" % status

        if project:
            projects = [project, ]
        else:
            projects = self.projects

        for project in projects:
            tablename = self._tablename(project)
            for each in self._select2dic(tablename, what=fields, where=where):
                yield self._parse(each)

    def get_task(self, project, taskid, fields=None):
        if project not in self.projects:
            self._list_project()
        if project not in self.projects:
            return None
        where = "`taskid` = %s" % self.placeholder
        if project not in self.projects:
            return None
        tablename = self._tablename(project)
        for each in self._select2dic(tablename, what=fields, where=where, where_values=(taskid, )):
            return self._parse(each)
        return None

    def status_count(self, project):
        '''
        return a dict
        '''
        result = dict()
        if project not in self.projects:
            self._list_project()
        if project not in self.projects:
            return result
        tablename = self._tablename(project)
        for status, count in self._execute("SELECT `status`, count(1) FROM %s GROUP BY `status`" %
                                           self.escape(tablename)):
            result[status] = count
        return result

    def insert(self, project, taskid, obj={}):
        if project not in self.projects:
            self._create_project(project)
            self._list_project()
        obj = dict(obj)
        obj['taskid'] = taskid
        obj['project'] = project
        obj['updatetime'] = time.time()
        tablename = self._tablename(project)
        return self._insert(tablename, **self._stringify(obj))

    def update(self, project, taskid, obj={}, **kwargs):
        if project not in self.projects:
            raise LookupError
        tablename = self._tablename(project)
        obj = dict(obj)
        obj.update(kwargs)
        obj['updatetime'] = time.time()
        return self._update(
            tablename, where="`taskid` = %s" % self.placeholder, where_values=(taskid, ),
            **self._stringify(obj)
        )
