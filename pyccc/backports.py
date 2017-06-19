from __future__ import print_function, absolute_import, division
from future.builtins import *
from future import standard_library, builtins
standard_library.install_aliases()

# Copyright 2017 Autodesk Inc.
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

from future.utils import PY2

from codecs import BOM_UTF8, lookup
import re
import inspect


if PY2:
    # This is only necessary for Python 2, it's taken care of in Python 3

    cookie_re = re.compile(r'^[ \t\f]*#.*?coding[:=][ \t]*([-\w.]+)', re.ASCII)
    blank_re = re.compile(br'^[ \t\f]*(?:[#\r\n]|$)', re.ASCII)

    def detect_encoding(readline):
        """
        The detect_encoding() function is used to detect the encoding that should
        be used to decode a Python source file.  It requires one argument, readline,
        in the same way as the tokenize() generator.
        It will call readline a maximum of twice, and return the encoding used
        (as a string) and a list of any lines (left as bytes) it has read in.
        It detects the encoding from the presence of a utf-8 bom or an encoding
        cookie as specified in pep-0263.  If both a bom and a cookie are present,
        but disagree, a SyntaxError will be raised.  If the encoding cookie is an
        invalid charset, raise a SyntaxError.  Note that if a utf-8 bom is found,
        'utf-8-sig' is returned.
        If no encoding is specified, then the default of 'utf-8' will be returned.

        Note:
            Copied without modificaiton from Python 3.6.1 tokenize standard library module

            Copyright (c) 2001, 2002, 2003, 2004, 2005, 2006, 2007, 2008, 2009, 2010,
            2011, 2012, 2013, 2014, 2015, 2016, 2017 Python Software Foundation; All Rights
            Reserved"

            See also py-cloud-compute-cannon/NOTICES.
        """
        try:
            filename = readline.__self__.name
        except AttributeError:
            filename = None
        bom_found = False
        encoding = None
        default = 'utf-8'
        def read_or_stop():
            try:
                return readline()
            except StopIteration:
                return b''

        def find_cookie(line):
            try:
                # Decode as UTF-8. Either the line is an encoding declaration,
                # in which case it should be pure ASCII, or it must be UTF-8
                # per default encoding.
                line_string = line.decode('utf-8')
            except UnicodeDecodeError:
                msg = "invalid or missing encoding declaration"
                if filename is not None:
                    msg = '{} for {!r}'.format(msg, filename)
                raise SyntaxError(msg)

            match = cookie_re.match(line_string)
            if not match:
                return None
            encoding = _get_normal_name(match.group(1))
            try:
                codec = lookup(encoding)
            except LookupError:
                # This behaviour mimics the Python interpreter
                if filename is None:
                    msg = "unknown encoding: " + encoding
                else:
                    msg = "unknown encoding for {!r}: {}".format(filename,
                            encoding)
                raise SyntaxError(msg)

            if bom_found:
                if encoding != 'utf-8':
                    # This behaviour mimics the Python interpreter
                    if filename is None:
                        msg = 'encoding problem: utf-8'
                    else:
                        msg = 'encoding problem for {!r}: utf-8'.format(filename)
                    raise SyntaxError(msg)
                encoding += '-sig'
            return encoding

        first = read_or_stop()
        if first.startswith(BOM_UTF8):
            bom_found = True
            first = first[3:]
            default = 'utf-8-sig'
        if not first:
            return default, []

        encoding = find_cookie(first)
        if encoding:
            return encoding, [first]
        if not blank_re.match(first):
            return default, [first]

        second = read_or_stop()
        if not second:
            return default, [first]

        encoding = find_cookie(second)
        if encoding:
            return encoding, [first, second]

        return default, [first, second]


def _get_normal_name(orig_enc):
    """Imitates get_normal_name in tokenizer.c.

    Note:
        Copied without modification from Python 3.6.1 tokenize standard library module

        Copyright (c) 2001, 2002, 2003, 2004, 2005, 2006, 2007, 2008, 2009, 2010,
        2011, 2012, 2013, 2014, 2015, 2016, 2017 Python Software Foundation; All Rights
        Reserved"

        See also py-cloud-compute-cannon/NOTICES.
    """
    # Only care about the first 12 characters.
    enc = orig_enc[:12].lower().replace("_", "-")
    if enc == "utf-8" or enc.startswith("utf-8-"):
        return "utf-8"
    if enc in ("latin-1", "iso-8859-1", "iso-latin-1") or \
       enc.startswith(("latin-1-", "iso-8859-1-", "iso-latin-1-")):
        return "iso-8859-1"
    return orig_enc


def getclosurevars(func):
    """
    Get the mapping of free variables to their current values.

    Returns a named tuple of dicts mapping the current nonlocal, global
    and builtin references as seen by the body of the function. A final
    set of unbound names that could not be resolved is also provided.

    Note:
        Modified function from the Python 3.5 inspect standard library module

        Copyright (c) 2001, 2002, 2003, 2004, 2005, 2006, 2007, 2008, 2009, 2010,
        2011, 2012, 2013, 2014, 2015, 2016, 2017 Python Software Foundation; All Rights
        Reserved"

        See also py-cloud-compute-cannon/NOTICES.
    """
    if inspect.ismethod(func):
        func = func.__func__

    elif not inspect.isroutine(func):
        raise TypeError("'{!r}' is not a Python function".format(func))

    # AMVMOD: deal with python 2 builtins that don't define these
    code = getattr(func, '__code__', None)
    closure = getattr(func, '__closure__', None)
    co_names = getattr(code, 'co_names', ())
    glb = getattr(func, '__globals__', {})

    # Nonlocal references are named in co_freevars and resolved
    # by looking them up in __closure__ by positional index
    if closure is None:
        nonlocal_vars = {}
    else:
        nonlocal_vars = {var: cell.cell_contents
                         for var, cell in zip(code.co_freevars, func.__closure__)}

    # Global and builtin references are named in co_names and resolved
    # by looking them up in __globals__ or __builtins__
    global_ns = glb
    builtin_ns = global_ns.get("__builtins__", builtins.__dict__)
    if inspect.ismodule(builtin_ns):
        builtin_ns = builtin_ns.__dict__
    global_vars = {}
    builtin_vars = {}
    unbound_names = set()
    for name in co_names:
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

    return {'nonlocal': nonlocal_vars,
            'global': global_vars,
            'builtin': builtin_vars,
            'unbound': unbound_names}

