#!/usr/bin/env python
# -*- coding: utf-8 -*-


import os
import time

basedir = '..'
filelists = []
# 指定想要统计的文件类型
whitelist = ['js', 'py']


# 遍历文件
def getFile(basedir):
    global filelists
    for parent, dirnames, filenames in os.walk(basedir):
        for filename in filenames:
            ext = filename.split('.')[-1]
            # 只统计指定的文件类型，略过一些log和cache文件
            if ext in whitelist:
                filelists.append(os.path.join(parent, filename))


# 统计一个文件的行数
def countLine(fname):
    count = 0
    with open(fname) as objfile:
        for file_line in objfile.xreadlines():
            if file_line != '' and file_line != '\n':  # 过滤掉空行
                count += 1
    print fname + '----', count
    return count


if __name__ == '__main_':
    startTime = time.clock()
    getFile(basedir)
    totalline = 0
    for filelist in filelists:
        totalline = totalline + countLine(filelist)
    print "total files:%d, total lines:%d, average lines:%d" % (len(filelists), totalline, totalline / len(filelists))
    print 'Done! Cost Time: %0.2f second' % (time.clock() - startTime)
if __name__ == '__main__':
    import Queue
    from collections import deque

    q = deque()
    q.append(1)
    q.append(3)
    q.append(6)
    print "s:", sum(q)
