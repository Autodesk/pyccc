# Copyright 2016 Autodesk Inc.
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


import inspect
import linecache
import re
import string
from collections import namedtuple
import future_builtins as builtins

__author__ = 'aaronvirshup'


def getsource(classorfunc):
    try:
        source = inspect.getsource(classorfunc)
    except TypeError:  # raised if defined in __main__ - use fallback to get the source instead
        source = getsourcefallback(classorfunc)

    declaration = []
    sourcefile = []
    found_decl = False
    # Strip function decorators, separate declaration from code
    for iline, line in enumerate(source.split('\n')):
        if iline == 0 and line.strip().startswith('@'): continue
        if found_decl:
            sourcefile.append(line)
        else:
            cind = line.find(':')
            if cind > 0:
                found_decl = True
                declaration.append(line[:cind + 1])
                after_decl = line[cind + 1:].strip()
            else:
                declaration.append(line)

    # If it's a class, make sure we import its superclasses
    # Unfortunately, we need to modify the code to make sure the
    # parent classes have the correct names
    # TODO: find a better way to do this without having to parse code
    if type(classorfunc) == type:
        cls = classorfunc
        base_imports = {}
        for base in cls.__bases__:
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
        declaration = [impstring for c, impstring in base_imports.iteritems()
                       if c.__module__ != '__builtin__']
        declaration.append(declstring)

    else:
        declaration[-1] += after_decl

    return '\n'.join(declaration + sourcefile)


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
            "This class doesn't have an instance method, create one to cloudify it")

    ### This part is derived from inspect.findsource ###
    module = inspect.getmodule(cls)
    file = inspect.getfile(imethod)
    lines = linecache.getlines(file, module.__dict__)
    name = cls.__name__
    pat = re.compile(r'^(\s*)class\s*'+name+r'\b')

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

    #### this is what inspect.getsourcelines does ###
    glines = inspect.getblock(flines[flnum:])

    ### And this is what inspect.getsource does ###
    return string.join(glines,"")


ClosureVars = namedtuple('ClosureVars', 'nonlocals globals builtins unbound')


def getclosurevars(func):
    """
    NOTE: this is "backported" (copied verbatim) from the python3 inspect module

    Get the mapping of free variables to their current values.

    Returns a named tuple of dicts mapping the current nonlocal, global
    and builtin references as seen by the body of the function. A final
    set of unbound names that could not be resolved is also provided.
    """

    if inspect.ismethod(func):
        func = func.__func__

    if not inspect.isfunction(func):
        raise TypeError("'{!r}' is not a Python function".format(func))

    code = func.__code__
    # Nonlocal references are named in co_freevars and resolved
    # by looking them up in __closure__ by positional index
    if func.__closure__ is None:
        nonlocal_vars = {}
    else:
        nonlocal_vars = {var: cell.cell_contents
                         for var, cell in zip(code.co_freevars, func.__closure__)}

    # Global and builtin references are named in co_names and resolved
    # by looking them up in __globals__ or __builtins__
    global_ns = func.__globals__
    builtin_ns = global_ns.get("__builtins__", builtins.__dict__)
    if inspect.ismodule(builtin_ns):
        builtin_ns = builtin_ns.__dict__
    global_vars = {}
    builtin_vars = {}
    unbound_names = set()
    for name in code.co_names:
        if name in ("None", "True", "False"):
            # Because these used to be builtins instead of keywords, they
            # may still show up as name references. We ignore them.
            continue
        try:
            global_vars[name] = global_ns[name]
        except KeyError:
            try:
                builtin_vars[name] = builtin_ns[name]
            except KeyError:
                unbound_names.add(name)

    return ClosureVars(nonlocal_vars, global_vars,
                       builtin_vars, unbound_names)