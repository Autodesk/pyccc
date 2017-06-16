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
Functions to that allow python commands to be run as jobs with the platform API
"""
from __future__ import print_function, unicode_literals, absolute_import, division
from future import standard_library
standard_library.install_aliases()
from future.builtins import *

import sys
import pickle
import inspect

import pyccc
from . import job
from . import source_inspections as src
from .exceptions import ProgramFailure
from .files import StringContainer, LocalFile
from . import picklers

from ._native import native


def exports(o):
    __all__.append(o.__name__)
    return o
__all__ = []


PYTHON_JOB_FILE = LocalFile('%s/static/run_job.py' % pyccc.PACKAGE_PATH)
DEFAULT_INTERPRETER = 'python%s' % sys.version_info.major
PICKLE_PROTOCOL = 2  # required for 2/3 compatibile pickle objects

if sys.version_info.major == 2:
    PYVERSION = 2
    import __builtin__ as BUILTINS
else:
    assert sys.version_info.major == 3
    PYVERSION = 3
    import builtins as BUILTINS


@exports
class PythonCall(object):
    def __init__(self, function, *args, **kwargs):
        self.function = function
        self.args = args
        self.kwargs = kwargs

        try:
            cls = function.__self__.__class__
        except AttributeError:
            self.is_instancemethod = False
        else:
            if function.__self__ == BUILTINS or function.__self__ is None:
                self.is_instancemethod = False
            else:
                self.is_instancemethod = True


@exports
class PythonJob(job.Job):

    # @utils.doc_inherit
    def __init__(self, engine, image, command,
                 interpreter=DEFAULT_INTERPRETER,
                 persist_references=False,
                 sendsource=True, **kwargs):
        self._raised = False
        self._updated_object = None
        self._exception = None
        self._traceback = None
        self.sendsource = sendsource
        self._function_result = None
        self.interpreter = self._clean_interpreter_string(interpreter)
        self.persist_references = persist_references

        self.function_call = command

        if 'inputs' not in kwargs:
            kwargs['inputs'] = {}
        inputs = kwargs['inputs']

        # assemble the commands to run
        python_files = self._get_python_files()
        inputs.update(python_files)

        command = '%s run_job.py' % self.interpreter

        super(PythonJob, self).__init__(engine, image, command,
                                        **kwargs)

    @staticmethod
    def _clean_interpreter_string(istr):
        try:
            float(istr)
        except ValueError:
            return istr
        else:
            return 'python' + str(istr)

    def _get_python_files(self):
        """
        Construct the files to send the remote host

        Returns:
             dict: dictionary of filenames and file objects
        """
        python_files = {'run_job.py': PYTHON_JOB_FILE}

        remote_function = PackagedFunction(self.function_call, self.persist_references)
        if self.persist_references:
            dumps = picklers.departure_dumps
        else:
            dumps = pickle.dumps

        python_files['function.pkl'] = pyccc.BytesContainer(
                dumps(remote_function, protocol=PICKLE_PROTOCOL),
                name='function.pkl')
        self._remote_function = remote_function

        sourcefile = StringContainer(self._get_source(),
                                     name='source.py')

        python_files['source.py'] = sourcefile
        return python_files

    def _get_source(self, remote_function=None):
        """
        Calls the appropriate source inspection to get any required source code

        Will also get code for any functions referenced via closure (currently one level deep only)

        Returns:
             bytes: utf-8 encoded source code
        """
        if self.sendsource:
            func = self.function_call.function
            if self.function_call.is_instancemethod:
                obj = func.__self__.__class__
            else:
                obj = func
            srclines = [src.getsource(obj)]
        elif self.function_call.is_instancemethod:
            srclines = ['']
        else:
            srclines = ["from %s import %s\n"%(self.function_call.function.__module__,
                                               self.function_call.function.__name__)]

        if remote_function is not None and remote_function.global_functions:
            for name, f in remote_function.global_functions.items():
                srclines.append('\n# source code for function "%s"' % name)
                srclines.append(src.getsource(f))

        # This is the only source code needed from pyccc
        srclines.append(PACKAGEDFUNCTIONSOURCE)

        if isinstance(srclines, str):
            srclines = b'# -*- coding: utf-8 -*-\n' + srclines.encode('utf-8')
        return '\n'.join(srclines)

    @property
    def result(self):
        """The return value of the callback function if provided, or ``self.function_result`` if not
        """
        self._finish_job()

        if self.when_finished is None:
            return self.function_result
        else:
            return self._callback_result

    @property
    def function_result(self):
        """ The return value of the called python function
        """
        self._finish_job()
        if self._function_result is None:
            self.reraise_remote_exception(force=True)  # there's no result to return
            try:
                returnval = self.get_output('_function_return.pkl')
            except KeyError:
                raise ProgramFailure(self)
            if self.persist_references:
                loads = picklers.return_loads
            else:
                loads = pickle.loads

            self._function_result = loads(returnval.read('rb'))
        return self._function_result

    @property
    def updated_object(self):
        """
        If the function was an object's method, return the new state of the object
        Will re-raise any exceptions raised remotely
        """
        if self._updated_object is None:
            self.reraise_remote_exception()
            self._updated_object = pickle.loads(self.get_output('_object_state.pkl').read('rb'))
        return self._updated_object

    @property
    def exception(self):
        """
        The exception object, if any, from the remote execution
        """
        if self._exception is None:
            if 'exception.pkl' in self.get_output():
                self._raised = False
                try:
                    self._exception = pickle.loads(self.get_output('exception.pkl').read('rb'))
                except Exception as exc:  # catches errors in unpickling the exception
                    self._exception = exc
                self._traceback = self.get_output('traceback.txt').read()
            else:
                self._exception = False
        return self._exception

    def reraise_remote_exception(self, force=False):
        """
        Raises exceptions from the remote execution
        """
        # TODO: include debugging info / stack variables using tblib? - even if possible, this won't work without deps
        import tblib
        if (force or not self._raised) and self.exception:
            self._raised = True
            raise self._exception


# Note: PackagedFunction does NOT inherit from `future.builtins.object` - that would introduce a
# dependency on the `future` package when we try to run this remotely. Instead, we just use the
# interpreter's built-in `object` type.
class PackagedFunction(native.object):
    """
    This object captures enough information to serialize, deserialize, and run a
    python function

    Specifically, this creates an object that, after pickling, can be unpickled and run,
    and behave in *basically* the same way as the original function. HOWEVER, the function's
    source code must be sent separately - that part can't be pickled.

    Notes:
        - This is *designed* to execute arbitrary code. Use with trusted sources only!
        - This will work best with *pure* functions operating on well-behaved python objects.
        - All relevant variables and arguments need to be pickle-able.
        - Object methods that only operate on the object itself can be considered "pure".
        - Function side effects are not tracked at all.
        - Closure variables and module references will be sent along with the function
    """
    def __init__(self, function_call, persist_references):
        func = function_call.function
        self.is_imethod = function_call.is_instancemethod
        if self.is_imethod:
            self.obj = func.__self__
            self.imethod_name = func.__name__
        else:
            self.func_name = func.__name__
        self.args = function_call.args
        self.kwargs = function_call.kwargs
        self.persist_references = persist_references

        globalvars = src.get_global_vars(func)
        self.global_closure = globalvars['vars']
        self.global_modules = globalvars['modules']
        self.global_functions = globalvars['functions']

    def run(self, func=None):
        """
        Evaluates the packaged function as func(*self.args,**self.kwargs)
        If func is a method of an object, it's accessed as getattr(self.obj,__name__).
        If it's a user-defined function, it needs to be passed in here because it can't
        be serialized.

        Returns:
            object: function's return value
        """
        to_run = self.prepare_namespace(func)
        result = to_run(*self.args, **self.kwargs)
        return result

    def prepare_namespace(self, func):
        """
        Prepares the function to be run after deserializing it.
        Re-associates any previously bound variables and modules from the closure

        Returns:
            callable: ready-to-call function
        """
        if self.is_imethod:
            to_run = getattr(self.obj, self.imethod_name)
        else:
            to_run = func

        for varname, modulename in self.global_modules.items():
            to_run.__globals__[varname] = __import__(modulename)
        if self.global_closure:
            to_run.__globals__.update(self.global_closure)
        if self.global_functions:
            to_run.__globals__.update(self.global_functions)
        return to_run

PACKAGEDFUNCTIONSOURCE = '\n'.join(['',
                                    src.getsource(PackagedFunction),
                                    '\nimport pickle',
                                    src.getsource(picklers.ReturningPickler)])
