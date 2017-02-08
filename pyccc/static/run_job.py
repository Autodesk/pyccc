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
"""
import sys
import os
import cPickle as cp
import traceback as tb
import time

start_time = time.time()

import source  # the dynamically created source file


RENAMETABLE = {'pyccc.python': 'source',
               '__main__': 'source'}


def main():
    os.environ['IS_PYCCC_JOB'] = '1'
    try:
        funcpkg, func = load_job()
        result = funcpkg.run(func)
        serialize_output(result,
                         separate_fields=funcpkg._separate_io_fields is not None)

        if funcpkg.is_imethod:
            with open('_object_state.pkl', 'w') as ofp:
                cp.dump(funcpkg.obj, ofp, cp.HIGHEST_PROTOCOL)

    # Catch all exceptions and return them to the client
    except Exception as exc:
        capture_exceptions(exc)

    print 'Python execution walltime:', time.time() - start_time


def load_job():
    with open('function.pkl', 'r') as pf:
        funcpkg = unpickle_with_remap(pf)

    if funcpkg._separate_io_fields:
        inputs = {}
        for field in funcpkg._separate_io_fields:
            with open('inputs/%s.pkl' % field, 'r') as infile:
                inputs[field] = cp.load(infile)
        funcpkg.kwargs = inputs

    if hasattr(funcpkg, 'func_name'):
        func = getattr(source, funcpkg.func_name)
    else:
        func = None

    return funcpkg, func


def serialize_output(result, separate_fields=False):
    if separate_fields:
        if not os.path.isdir('outputs'):
            os.mkdir('outputs')

        if result is None: result = {}

        for field, value in result.iteritems():
            with open('outputs/%s.pkl' % field, 'w') as rp:
                cp.dump(value, rp)

        with open('outputfields.txt', 'w') as outf:
            for field in result.iterkeys():
                print >> outf, field
    else:
        with open('_function_return.pkl', 'w') as rp:
            cp.dump(result, rp, cp.HIGHEST_PROTOCOL)


def capture_exceptions(exc):
    if len(sys.argv) > 1 and sys.argv[1] == '--debug':
        raise  # for debugging in a container
    with open('exception.pkl', 'w') as excfile:
        cp.dump(exc, excfile)
    with open('traceback.txt', 'w') as tbfile:
        tb.print_exc(file=tbfile)


def unpickle_with_remap(fileobj):
    """ This function remaps pickled classnames. It's specifically here to remap the
    "PackagedFunction" class from pyccc to the __main__ module.

    References:
        Based on https://wiki.python.org/moin/UsingPickle/RenamingModules
    """
    import pickle

    try:
        from cStringIO import StringIO
    except ImportError:
        from StringIO import StringIO

    def mapname(name):
        if name in RENAMETABLE:
            return RENAMETABLE[name]
        return name

    def mapped_load_global(self):
        module = mapname(self.readline()[:-1])
        name = mapname(self.readline()[:-1])
        klass = self.find_class(module, name)
        self.append(klass)

    unpickler = pickle.Unpickler(fileobj)
    unpickler.dispatch[pickle.GLOBAL] = mapped_load_global
    return unpickler.load()


if __name__ == '__main__':
    main()



