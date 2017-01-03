#!/usr/bin/env python
# -*- encoding: utf-8 -*-



class ListO(object):

    """A StringO write to list."""

    def __init__(self, buffer=None):
        self._buffer = buffer
        if self._buffer is None:
            self._buffer = []

    def isatty(self):
        return False

    def close(self):
        pass

    def flush(self):
        pass

    def seek(self, n, mode=0):
        pass

    def readline(self):
        pass

    def reset(self):
        pass

    def write(self, x):
        self._buffer.append(x)

    def writelines(self, x):
        self._buffer.extend(x)
