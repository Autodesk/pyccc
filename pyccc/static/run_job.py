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

PICKLE_PROTOCOL = 2  # required for 2/3 compatible pickle objects


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
            It's been modified for 2/3 cross-compatibility
        """
        modname = self.RENAMETABLE.get(module, module)

        try:
            # can't use ``super`` here (not 2/3 compatible)
            klass = pickle.Unpickler.find_class(self, modname, name)

        except ImportError:
            if hasattr(source, name):
                newmod = types.ModuleType(modname)
                sys.modules[modname] = newmod
                setattr(newmod, name, getattr(source, name))
            klass = self.find_class(modname, name)

        klass.__module__ = module
        return klass


if __name__ == '__main__':
    import source  # this is the dynamically created source module
    os.environ['IS_PYCCC_JOB'] = '1'
    try:
        # Deserialize and set up the packaged function (see pyccc.python.PackagedFunction)
        with open('function.pkl', 'rb') as pf:
            job = MappedUnpickler(pf).load()

        if not hasattr(job, 'obj'):  # it's a standalone function
            func = getattr(source, job.__name__)
        else:  # it's an instance method
            func = None

        # Run the function!
        result = job.run(func)

        # Serialize the results
        with open('_function_return.pkl', 'wb') as rp:
            pickle.dump(result, rp, PICKLE_PROTOCOL)
        if job.is_imethod:
            with open('_object_state.pkl', 'wb') as ofp:
                pickle.dump(job.obj, ofp, PICKLE_PROTOCOL)

    # Catch exception, save it, raise
    except Exception as exc:
        with open('exception.pkl', 'wb') as excfile:
            pickle.dump(exc, excfile, PICKLE_PROTOCOL)
        with open('traceback.txt', 'w') as tbfile:
            tb.print_exc(file=tbfile)

        raise


