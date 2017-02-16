#!/usr/bin/env python
# -*- encoding: utf-8 -*-

import re
import six
import json
import mysql.connector
from datetime import datetime

from sspider.libs import utils
from sspider.database.base.resultdb import ResultDB as BaseResultDB
from sspider.database.basedb import BaseDB
from .mysqlbase import MySQLMixin, SplitTableMixin


class ResultDB(MySQLMixin, SplitTableMixin, BaseResultDB, BaseDB):
    __tablename__ = 'resultdb'

    def __init__(self, host='localhost', port=3306, database='resultdb',
                 user='root', passwd=123):
        self.database_name = database
        self.conn = mysql.connector.connect(user=user, password=passwd,
                                            host=host, port=port, autocommit=True)
        if database not in [x[0] for x in self._execute('show databases')]:
            self._execute('CREATE DATABASE %s' % self.escape(database))
        self.conn.database = database
        self._list_project()

    def _create_project(self, project):
        assert re.match(r'^\w+$', project) is not None
        tablename = self._tablename(project)
        if tablename in [x[0] for x in self._execute('show tables')]:
            return
        self._execute('''CREATE TABLE %s (
                    `id` int NOT NULL PRIMARY KEY AUTO_INCREMENT,
                    `url_hash` varchar(64) NOT NULL UNIQUE,
                    `url` varchar(1024) NOT NULL,
                    `type` varchar(64),
                    `param` MEDIUMBLOB,
                    `seed_url` varchar(1024),
                    `updatetime` DATETIME
                    ) ENGINE=InnoDB CHARSET=utf8''' % self.escape(tablename))

    def _parse(self, data):
        for key, value in list(six.iteritems(data)):
            if isinstance(value, (bytearray, six.binary_type)):
                data[key] = utils.text(value)
        if 'result' in data:
            data['result'] = json.loads(data['result'])
        return data

    def _stringify(self, data):
        if 'param' in data:
            data['param'] = json.dumps(data['param'])
        return data

    def save(self, project, result):
        tablename = self._tablename(project)
        self._list_project()
        if project not in self.projects:
            self._create_project(project)
            self._list_project()
        obj = {
            'url_hash': utils.md5string(result['url']),
            'url': result['url'],
            'type': result['type'],
            'param': result['param'],
            'seed_url': result['seed_url'],
            'updatetime': datetime.now()
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
