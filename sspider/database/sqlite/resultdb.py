#!/usr/bin/env python
# -*- encoding: utf-8 -*-

import re
import time
import json

import sys,os
DATABASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if DATABASE_DIR not in sys.path:
    sys.path.append(DATABASE_DIR)

from sspider.libs import utils
from sqlitebase import SQLiteMixin, SplitTableMixin
from sspider.database.base.taskdb import TaskDB as BaseResultDB
from sspider.database.basedb import BaseDB


class ResultDB(SQLiteMixin, SplitTableMixin, BaseResultDB, BaseDB):
    __tablename__ = 'resultdb'
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
                        id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                        url_hash NOT NULL UNIQUE,
                        url,
                        type,
                        param,
                        seed_url,
                        status,
                        updatetime
                        )''' % tablename)

    def _parse(self, data):
        if 'result' in data:
            data['result'] = json.loads(data['result'])
        return data

    def _stringify(self, data):
        if 'param' in data:
            data['param'] = json.dumps(data['param'])
        return data

    def save(self, project, result):
        tablename = self._tablename(project)
        if project not in self.projects:
            self._create_project(project)
            self._list_project()
        obj = {
            'url_hash': utils.md5string(result['url']),
            'url': result['url'],
            'type': result['type'],
            'param': result['param'],
            'seed_url': result['seed_url'],
            'status': 0,
            'updatetime': time.time()
        }
        return self._replace(tablename, **self._stringify(obj))

    def select(self, project, fields=None, offset=0, limit=None):
        if project not in self.projects:
            self._list_project()
        if project not in self.projects:
            return
        tablename = self._tablename(project)

        for task in self._select2dic(tablename, what=fields, order='updatetime DESC',
                                     offset=offset, limit=limit):
            yield self._parse(task)

    def count(self, project):
        if project not in self.projects:
            self._list_project()
        if project not in self.projects:
            return 0
        tablename = self._tablename(project)
        for count, in self._execute("SELECT count(1) FROM %s" % self.escape(tablename)):
            return count

    def get(self, project, url, fields=None):
        if project not in self.projects:
            self._list_project()
        if project not in self.projects:
            return
        tablename = self._tablename(project)
        where = "`url` = %s" % self.placeholder
        for task in self._select2dic(tablename, what=fields,
                                     where=where, where_values=(url,)):
            return self._parse(task)

    def finish(self, project):
        if project not in self.projects:
            self._list_project()
        if project not in self.projects:
            return
        tablename = self._tablename(project)
        where = "1=1"
        value = {"status": 1}
        return self._update(tablename=tablename, where=where, **value)
