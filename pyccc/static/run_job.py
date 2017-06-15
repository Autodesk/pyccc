#!/usr/bin/env python
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
This is a script that drives the remote computation of a function or instance method.
It's designed to use the pickled objects produced by the PythonJob class

Note:
    This script must be able to run in both Python 2.7 and 3.5+ *without any dependencies*
"""
from __future__ import print_function, unicode_literals, absolute_import, division
import os
import types
import sys
import pickle
import traceback as tb

import source  # the dynamically created source file

PICKLE_PROTOCOL = 2  # required for 2/3 compatible pickle objects

RENAMETABLE = {'pyccc.python': 'source',
               '__main__': 'source'}

if sys.version_info.major == 2:
    PYVERSION = 2
    import __builtin__ as BUILTINS
else:
    assert sys.version_info.major == 3
    PYVERSION = 3
    import builtins as BUILTINS


def main():
    os.environ['IS_PYCCC_JOB'] = '1'
    try:
        funcpkg, func = load_job()
        result = funcpkg.run(func)
        serialize_output(result, persistrefs=funcpkg.persist_references)

        if funcpkg.is_imethod:
            with open('_object_state.pkl', 'wb') as ofp:
                pickle.dump(funcpkg.obj, ofp, PICKLE_PROTOCOL)

    # Catch all exceptions and return them to the client
    except Exception as exc:
        capture_exceptions(exc)
        raise


def load_job():
    with open('function.pkl', 'rb') as pf:
        funcpkg = MappedUnpickler(pf).load()

    if hasattr(funcpkg, 'func_name'):
        try:
            func = getattr(source, funcpkg.func_name)
        except AttributeError:
            func = getattr(BUILTINS, funcpkg.func_name)
    else:
        func = None

    return funcpkg, func


def serialize_output(result, persistrefs=False):
    with open('_function_return.pkl', 'wb') as rp:
        if persistrefs:
            pickler = source.ReturningPickler(rp, PICKLE_PROTOCOL)
            pickler.dump(result)
        else:
            pickle.dump(result, rp, PICKLE_PROTOCOL)


def capture_exceptions(exc):
    with open('exception.pkl', 'wb') as excfile:
        pickle.dump(exc, excfile, protocol=PICKLE_PROTOCOL)
    with open('traceback.txt', 'w') as tbfile:
        tb.print_exc(file=tbfile)


class MappedUnpickler(pickle.Unpickler):
    RENAMETABLE = {'pyccc.python': 'source',
                   '__main__': 'source'}

    def find_class(self, module, name):
        """ This override is here to help pickle find the modules that classes are defined in.

        It does three things:
         1) remaps the "PackagedFunction" class from pyccc to the `source.py` module.
         2) Remaps any classes created in the client's '__main__' to the `source.py` module
         3) Creates on-the-fly modules to store any other classes present in source.py

        References:
                This is a modified version of the 2-only recipe from
                https://wiki.python.org/moin/UsingPickle/RenamingModules.
                It's been modified for 2/3 cross-compatibility    """
        import pickle

        modname = self.RENAMETABLE.get(module, module)

        try:
            # can't use ``super`` here (not 2/3 compatible)
            klass = pickle.Unpickler.find_class(self, modname, name)

        except (ImportError, RuntimeError):
            definition = getattr(source, name)
            newmod = _makemod(modname)
            sys.modules[modname] = newmod
            setattr(newmod, name, definition)
            klass = pickle.Unpickler.find_class(self, newmod.__name__, name)
            klass.__module__ = module
        return klass


def _makemod(name):
    fields = name.split('.')
    for i in range(0, len(fields)):
        tempname = str('.'.join(fields[0:i]))
        sys.modules[tempname] = types.ModuleType(tempname)
    return sys.modules[tempname]


if __name__ == '__main__':
    main()
