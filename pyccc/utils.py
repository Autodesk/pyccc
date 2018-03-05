# Copyright 2016-2018 Autodesk Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from __future__ import print_function, unicode_literals, absolute_import, division
from future import standard_library
standard_library.install_aliases()
from future.builtins import *

import sys
from io import StringIO
from functools import wraps
from uuid import uuid4
import tempfile
import shutil
import threading
import subprocess
import os

GIST_URL = "https://gist.github.com/avirshup/5dd7d5638acf245b2b1f"
RAW_GIST = 'https://gist.githubusercontent.com/avirshup/5dd7d5638acf245b2b1f/raw/'
MY_PATH = os.path.abspath(__file__)


def gist_diff():
    """Diff this file with the gist on github"""
    remote_file = wget(RAW_GIST)
    proc = subprocess.Popen(('diff - %s'%MY_PATH).split(),
                            stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE)
    stdout, stderr = proc.communicate(remote_file)
    return stdout


def wget(url):
    """
    Download the page into a string
    """
    import urllib.parse
    request = urllib.request.urlopen(url)
    filestring = request.read()
    return filestring


def if_not_none(item, default):
    if item is None:
        return default
    else:
        return item


def autodecode(b):
    """ Try to decode ``bytes`` to text - try default encoding first, otherwise try to autodetect

    Args:
        b (bytes): byte string

    Returns:
        str: decoded text string
    """
    import warnings
    import chardet

    try:
        return b.decode()
    except UnicodeError:
        result = chardet.detect(b)
        if result['confidence'] < 0.95:
            warnings.warn('autodecode failed with utf-8; guessing %s' % result['encoding'])
        return result.decode(result['encoding'])


def can_use_widgets():
    """ Expanded from from http://stackoverflow.com/a/34092072/1958900
    """
    if 'IPython' not in sys.modules:
        # IPython hasn't been imported, definitely not
        return False
    from IPython import get_ipython

    # check for `kernel` attribute on the IPython instance
    if getattr(get_ipython(), 'kernel', None) is None:
        return False

    try:
        import ipywidgets as ipy
        import traitlets
    except ImportError:
        return False

    return True


class PipedFile(object):
    """
    Allows us to pass data by filesystem localpath without ever writing it to disk
    To prevent deadlock, we spawn a thread to write to the pipe
    Call it as a context manager:
    >>> with PipedFile(_conte_contentsname=_conten_contentsipepath:
    >>>     print open(pipepath,'r').read()
    """
    def __init__(self, fileobj, filename='pipe'):
        if type(fileobj) in (str, str):
            self.fileobj = StringIO(fileobj)
        else:
            self.fileobj = fileobj
        self.tempdir = None
        assert '/' not in filename,"Filename must not include directory"
        self.filename = filename

    def __enter__(self):
        self.tempdir = tempfile.mkdtemp()
        self.pipe_path = os.path.join(self.tempdir, self.filename)
        os.mkfifo(self.pipe_path)
        self.pipe_thread = threading.Thread(target=self._write_to_pipe)
        self.pipe_thread.start()
        return self.pipe_path

    def _write_to_pipe(self):
        with open(self.pipe_path,'w') as pipe:
            pipe.write(self.fileobj.read())

    def __exit__(self, type, value, traceback):
        if self.tempdir is not None:
            shutil.rmtree(self.tempdir)


def remove_directories(list_of_paths):
    """
    Removes non-leafs from a list of directory paths
    """
    found_dirs = set('/')
    for path in list_of_paths:
        dirs = path.strip().split('/')
        for i in range(2,len(dirs)):
            found_dirs.add( '/'.join(dirs[:i]) )

    paths = [ path for path in list_of_paths if
              (path.strip() not in found_dirs) and path.strip()[-1]!='/' ]
    return paths


class Categorizer(dict):
    """
    Create a dict of lists from an iterable, with dict keys given by keyfn
    """
    def __init__(self,keyfn,iterable):
        super(Categorizer,self).__init__()
        self.keyfn = keyfn
        for item in iterable:
            self.add(item)

    def add(self, item):
        key = self.keyfn(item)
        if key not in self:
            self[key] = []
        self[key].append(item)


def make_local_temp_dir():
    tempdir = '/tmp/%s' % uuid4()
    os.mkdir(tempdir)
    return tempdir


class DotDict(dict):
    """Dict with items accessible as attributes"""
    def __getattr__(self,item):
        return self[item]

    def __setattr__(self,item,val):
        self[item] = val


class Alias(object):
    """
    Descriptor that calls a child object's method.
    e.g.
    >>> class A(object):
    >>>     childkeys = Alias('child.keys')
    >>>     child = dict()
    >>>
    >>> a = A()
    >>> a.child['key'] = 'value'
    >>> a.childkeys() #calls a.child.keys(), returns ['key']
    """
    def __init__(self, objmethod):
        objname, methodname = objmethod.split('.')
        self.objname = objname
        self.methodname = methodname

    def __get__(self, instance, owner):
        proxied = getattr(instance, self.objname)
        return getattr(proxied,self.methodname)


class MarkdownTable(object):
    def __init__(self,*categories):
        self.categories = categories
        self.lines = []

    def add_line(self,obj):
        if hasattr(obj,'keys'):
            newline = [obj.get(cat,'') for cat in self.categories]
        else:
            assert len(obj) == len(self.categories)
            newline = obj
        self.lines.append(newline)

    def markdown(self,replace=None):
        if replace is None: replace = {}
        outlines = ['| '+' | '.join(self.categories)+' |',
                    '|-' +''.join('|-' for x in self.categories) + '|']

        for line in self.lines:
            nextline = [str(replace.get(val,val)) for val in line]
            outlines.append('| '+' | '.join(nextline)+' |')
        return '\n'.join(outlines)


# class ArgumentDecorator(decorator):
#     def __init__(self,function,
#                  allexcept=None,
#                  only=None,
#                  append_docstring=False):
#         """
#         Transfer parts of a call signature from one function to another.
#         Intended for use as a decorator
#         :param function: function to take the call signature from
#         :param allexcept: transfer all function parameters except these (mutually exclusive with only)
#         :type allexcept: list
#         :param only: only transfer these function parameters (mutually exclusive with allexcept)
#         :type allexcept: list
#         """
#         if allexcept is not None and only is not None:
#             raise ValueError(
#                 'Argument decorator should be called with EITHER "allexcept" or "only" OR neither')
#
#         argspec = inspect.getargspec(function)
#         args = set(argspec.args)
#         if only is not None:
#             only = set(only)
#             self.arg_bindings = {x:None for x in args if x not in only}
#             for a in only: assert a in args
#         elif allexcept is not None:
#             self.arg_bindings = {x:None for x in allexcept}
#             for a in allexcept: assert a in args
#         else:
#             self.arg_bindings = {}
#         self.append_docstring = append_docstring
#         self.parent_doc = self.mask_docstring(function)
#
#     def mask_docstring(self,function):
#         """
#         Eventually should parse docstring and remove documentation for hidden arguments.
#         For now, does nothing
#         """
#         return function.__doc__
#
#     def __call__(self,function):
#         """
#         Updates the function's call signature.
#         Appends original function's docstring if append_docstring=True
#         """
#         functools.update_wrapper(function, self.partial_func, [], [])
#         if self.append_docstring:
#             function.__doc__ += '\n'+self.parent_doc
#         return function
#
# # idiomatic decorator name
# args_from = ArgumentDecorator


class DictLike(object):
    __contains__ = Alias('children.__contains__')
    __getitem__ = Alias('children.__getitem__')
    __setitem__ = Alias('children.__setitem__')
    update = Alias('children.update')
    get = Alias('children.get')
    values = Alias('children.values')
    keys = Alias('children.keys')
    items = Alias('children.items')
    itervalues = Alias('children.itervalues')
    iteritems = Alias('children.iteritems')
    iterkeys = Alias('children.iterkeys')

    def __init__(self,**kwargs):
        self.children = {}
        self.children.update(kwargs)



class DocInherit(object):
    """
    Allows methods to inherit docstrings from their superclasses
    FROM http://code.activestate.com/recipes/576862/
    """
    def __init__(self, mthd):
        self.mthd = mthd
        self.name = mthd.__name__

    def __get__(self, obj, cls):
        if obj:
            return self.get_with_inst(obj, cls)
        else:
            return self.get_no_inst(cls)

    def get_with_inst(self, obj, cls):

        overridden = getattr(super(cls, obj), self.name, None)

        @wraps(self.mthd, assigned=('__name__','__module__'))
        def f(*args, **kwargs):
            return self.mthd(obj, *args, **kwargs)

        return self.use_parent_doc(f, overridden)

    def get_no_inst(self, cls):

        for parent in cls.__mro__[1:]:
            overridden = getattr(parent, self.name, None)
            if overridden: break

        @wraps(self.mthd, assigned=('__name__','__module__'))
        def f(*args, **kwargs):
            return self.mthd(*args, **kwargs)

        return self.use_parent_doc(f, overridden)

    def use_parent_doc(self, func, source):
        if source is None:
            raise NameError("Can't find '%s' in parents"%self.name)
        func.__doc__ = source.__doc__
        return func

#idiomatic decorator name
doc_inherit = DocInherit