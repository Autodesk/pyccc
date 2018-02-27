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
"""
Source code inspections for sending python code to workers
"""
from __future__ import print_function, absolute_import, division, unicode_literals

from future import standard_library, builtins
standard_library.install_aliases()
from future.builtins import *

from future.utils import PY2

import inspect
import linecache
import re

from .backports import getclosurevars
if PY2:
    from .backports import detect_encoding


def get_global_vars(func):
    """ Store any methods or variables bound from the function's closure

    Args:
        func (function): function to inspect

    Returns:
        dict: mapping of variable names to globally bound VARIABLES
    """
    closure = getclosurevars(func)
    if closure['nonlocal']:
        raise TypeError("Can't launch a job with closure variables: %s" %
                        closure['nonlocals'].keys())
    globalvars = dict(modules={},
                      functions={},
                      vars={})
    for name, value in closure['global'].items():
        if inspect.ismodule(value):  # TODO: deal FUNCTIONS from closure
            globalvars['modules'][name] = value.__name__
        elif inspect.isfunction(value) or inspect.ismethod(value):
            globalvars['functions'][name] = value
        else:
            globalvars['vars'][name] = value

    return globalvars


def getsource(classorfunc):
    """ Return the source code for a class or function.

    Notes:
        Returned source will not include any decorators for the object.
        This will only return the explicit declaration of the object, not any dependencies

    Args:
        classorfunc (type or function): the object to get the source code for

    Returns:
        str: text of source code (without any decorators). Note: in python 2, this returns unicode
    """
    if _isbuiltin(classorfunc):
        return ''

    try:
        source = inspect.getsource(classorfunc)
    except TypeError:  # raised if defined in __main__ - use fallback to get the source instead
        source = getsourcefallback(classorfunc)

    declaration = []

    lines = source.splitlines()
    if PY2 and not isinstance(source, unicode):
        encoding = detect_encoding(iter(lines).next)[0]
        sourcelines = (s.decode(encoding) for s in lines)
    else:
        sourcelines = iter(lines)

    # First, get the declaration
    found_keyword = False
    for line in sourcelines:
        words = line.split()
        if not words:
            continue
        if words[0] in ('def', 'class'):
            found_keyword = True
        if found_keyword:
            cind = line.find(':')
            if cind > 0:
                declaration.append(line[:cind + 1])
                after_decl = line[cind + 1:].strip()
                break
            else:
                declaration.append(line)

    bodylines = list(sourcelines)  # the rest of the lines are body

    # If it's a class, make sure we import its superclasses
    # Unfortunately, we need to modify the code to make sure the
    # parent classes have the correct names
    # TODO: find a better way to do this without having to parse code
    if type(classorfunc) == type:
        cls = classorfunc
        base_imports = {}
        for base in cls.__bases__:
            if base.__name__ == 'object' and base.__module__ == 'builtins':  # don't import `object`
                continue
            if base in base_imports:
                continue
            if base.__module__ == '__main__':
                continue
            base_imports[base] = 'from %s import %s' % (base.__module__, base.__name__)
        cind = declaration[0].index('class ')

        declstring = declaration[0][:cind] + 'class %s(%s):%s' % (
            cls.__name__,
            ','.join([base.__name__ for base in cls.__bases__]),
            after_decl)
        declaration = [impstring for c, impstring in base_imports.items()
                       if c.__module__ != '__builtin__']
        declaration.append(declstring)

    else:
        declaration[-1] += after_decl

    return '\n'.join(declaration + bodylines)


def getsourcefallback(cls):
    """ Fallback for getting the source of interactively defined classes (typically in ipython)

    This is basically just a patched version of the inspect module, in which
    we get the code by calling inspect.findsource on an *instancemethod* of
    a class for which inspect.findsource fails.
    """
    for attr in cls.__dict__:
        if inspect.ismethod(getattr(cls, attr)):
            imethod = getattr(cls, attr)
            break
    else:
        raise AttributeError(
            "Cannot get this class' source; it does not appear to have any methods")

    ### This part is derived from inspect.findsource ###
    module = inspect.getmodule(cls)
    file = inspect.getfile(imethod)
    lines = linecache.getlines(file, module.__dict__)
    name = cls.__name__
    pat = re.compile(r'^(\s*)class\s*'+name+r'\b')

    # AMVMOD: find the encoding (necessary for python 2 only)
    #if PY2:
    #    with open(file, 'rb') as infile:
    #        encoding = detect_encoding(infile.readline)[0]

    # make some effort to find the best matching class definition:
    # use the one with the least indentation, which is the one
    # that's most probably not inside a function definition.
    candidates = []
    toplevel = False
    for i in range(len(lines)):
        match = pat.match(lines[i])
        if match:
            # if it's at toplevel, it's already the best one
            if lines[i][0] == 'c':
                flines, flnum = lines, i
                toplevel = True
                break
            # else add whitespace to candidate list
            candidates.append((match.group(1), i))
    if candidates and not toplevel:
        # this will sort by whitespace, and by line number,
        # less whitespace first
        candidates.sort()
        flines, flnum = lines, candidates[0][1]
    elif not candidates and not toplevel:
        raise IOError('could not find class definition')
    ### end modified inspect.findsource ###

    # this is what inspect.getsourcelines does
    glines = inspect.getblock(flines[flnum:])

    # And this is what inspect.getsource does
    if False: #if PY2:
        return ("".join(glines)).decode(encoding)
    else:
        return "".join(glines)


def _isbuiltin(obj):
    if inspect.isbuiltin(obj):
        return True
    elif obj.__module__ in ('builtins', '__builtin__'):
        return True
    else:
        return False

