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
import cPickle as cp
import traceback as tb

if __name__ == '__main__':
    # Load any passed source libraries
    execfile('source.py')
    try:

        # Read in the packaged function
        with open('function.pkl', 'r') as pf:
            job = cp.load(pf)
        if hasattr(job, 'func_name'):
            func = globals()[job.func_name]
        else:
            func = None

        # Run the function!
        result = job.run(func)

        # Serialize the results
        with open('_function_return.pkl', 'w') as rp:
            cp.dump(result, rp, cp.HIGHEST_PROTOCOL)
        if job.is_imethod:
            with open('_object_state.pkl', 'w') as ofp:
                cp.dump(job.obj, ofp, cp.HIGHEST_PROTOCOL)

    # Catch all exceptions and return them to the client
    except Exception as exc:
        with open('exception.pkl', 'w') as excfile:
            cp.dump(exc, excfile)
        with open('traceback.txt', 'w') as tbfile:
            tb.print_exc(file=tbfile)
