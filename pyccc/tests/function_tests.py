# -*- coding: utf-8 -*-
# some variables for the global namespace
import sys
import collections
from itertools import chain
import random as rnd
import time
from inspect import ismodule as module_check


YVAR = 3


# test functions below
def fn(x):
    return x+1


# includes a global variable
def fn_withvar(x):
    return x+YVAR


# includes a global function
def fn_withfunc(iter1, iter2):
    return list(chain(iter1, iter2))


# includes a global module reference
def fn_withmod(d):
    return collections.OrderedDict(d)


# includes a renamed global module reference
def fn_with_renamed_mod():
    return [rnd.random() for i in range(10)]


# includes a renamed module attribute
def fn_with_renamed_attr(a):
    return module_check(a)


# prints and returns unicode
def fn_prints_unicode():
    print(u'Å')
    sys.stderr.write(u'µ')
    return u'¶'


def sleep_then_exit_38():
    time.sleep(5)
    sys.exit(38)


class Cls(object):
    def __init__(self):
        self.x = 0

    def increment(self, by=1):
        self.x += by
        return self.x
