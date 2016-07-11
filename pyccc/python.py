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
import cPickle as cp
import inspect

import pyccc
from pyccc import job
from pyccc import source_inspections as src
from pyccc.files import StringContainer, LocalFile


def exports(o):
    __all__.append(o.__name__)
    return o
__all__ = []


PYTHON_JOB_FILE = LocalFile('%s/static/run_job.py' % pyccc.PACKAGE_PATH)


class ProgramFailure(Exception): pass


@exports
class PythonCall(object):
    def __init__(self, function, *args, **kwargs):
        self.function = function
        self.args = args
        self.kwargs = kwargs

        try:
            temp = function.im_self.__class__
        except AttributeError:
            self.is_instancemethod = False
        else:
            self.is_instancemethod = True


@exports
class PythonJob(job.Job):
    SHELL_COMMAND = 'python2 run_job.py'

    # @utils.doc_inherit
    def __init__(self, engine, image, command, sendsource=True, **kwargs):
        self._raised = False
        self._updated_object = None
        self._exception = None
        self._traceback = None
        self.sendsource = sendsource
        self._function_result = None

        self.function_call = command

        if 'inputs' not in kwargs:
            kwargs['inputs'] = {}
        inputs = kwargs['inputs']

        # assemble the commands to run
        python_files = self._get_python_files()
        inputs.update(python_files)

        super(PythonJob, self).__init__(engine, image, self.SHELL_COMMAND,
                                        **kwargs)

    def _get_python_files(self):
        """
        Construct the files to send the remote host
        :return: dictionary of filenames and file objects
        """
        python_files = {'run_job.py': PYTHON_JOB_FILE}

        remote_function = PackagedFunction(self.function_call)
        python_files['function.pkl'] = StringContainer(cp.dumps(remote_function, protocol=2),
                                                       'function.pkl')

        sourcefile = StringContainer(self._get_source(), 'source.py')

        python_files['source.py'] = sourcefile
        return python_files

    def _get_source(self):
        """
        Calls the appropriate source inspection to get any required source code

        Returns:
             str: string containing source code. If the relevant code is unicode, it will be
             encoded as utf-8, with the encoding declared in the first line of the file
        """
        if self.sendsource:
            func = self.function_call.function
            if self.function_call.is_instancemethod:
                obj = func.im_self.__class__
            else:
                obj = func
            srclines = src.getsource(obj)
        elif self.function_call.is_instancemethod:
            srclines = ''
        else:
            srclines = "from %s import %s\n" % (self.function_call.function.__module__,
                                                self.function_call.function.__name__)

        # This is the only source code needed from pyccc
        srclines += PACKAGEDFUNCTIONSOURCE

        if isinstance(srclines, unicode):
            srclines = '# -*- coding: utf-8 -*-\n' + srclines.encode('utf-8')
        return srclines

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
                raise ProgramFailure('The remote python program crashed without throwing an '
                                     'exception. Please carefully examine the execution '
                                     'environment.')
            self._callback_result = cp.loads(returnval.read())
        return self._callback_result

    @property
    def updated_object(self):
        """
        If the function was an object's method, return the new state of the object
        Will re-raise any exceptions raised remotely
        """
        if self._updated_object is None:
            self.reraise_remote_exception()
            self._updated_object = cp.loads(self.get_output('_object_state.pkl').read())
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
                    self._exception = cp.loads(self.get_output('exception.pkl').read())
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
            raise self._exception, None, tblib.Traceback.from_string(self._traceback).as_traceback()


class PackagedFunction(object):
    """
    This object captures enough information to serialize, deserialize, and run a
    python function
    """
    def __init__(self, function_call):
        """
        Conduct and store enough introspection on the passed function and arguments so
        that they can be serialized and run elsewhere
        """
        # TODO: check whether pickled object can be successfully unpickled
        # i.e., make sure its functions and classes are defined in the
        # base code

        # Store the function, arguments (and its object if necessary)
        func = function_call.function
        self.is_imethod = hasattr(func, 'im_self')
        if self.is_imethod:
            self.obj = func.im_self
            self.imethod_name = func.__name__
        else:
            self.func_name = func.__name__
        self.args = function_call.args
        self.kwargs = function_call.kwargs

        # Store any methods or variables bound from the function's closure
        closure = src.getclosurevars(func)
        if closure.nonlocals:
            raise TypeError("Can't launch a job with closure variables: %s"%
                            closure.nonlocals.keys())
        self.global_closure = {}
        self.global_modules = {}
        for name, value in closure.globals.iteritems():
            if inspect.ismodule(value):
                self.global_modules[name] = value.__name__
            else:
                self.global_closure[name] = value

    def run(self, func=None):
        """
        Evaluates the packaged function as func(*self.args,**self.kwargs)
        If func is a method of an object, it's accessed as getattr(self.obj,func_name).
        If it's a user-defined function, it needs to be passed in here because it can't
        be serialized.
        :return: function's return value
        """
        to_run = self.prepare_namespace(func)
        result = to_run(*self.args, **self.kwargs)
        return result

    def prepare_namespace(self, func):
        """
        Prepares the function to be run after deserializing it.
        Re-associates any previously bound variables and modules from the closure
        :return: Prepared callable function
        """
        if self.is_imethod:
            to_run = getattr(self.obj, self.imethod_name)
        else:
            to_run = func

        for varname, modulename in self.global_modules.iteritems():
            exec ('import %s as %s' % (modulename, varname))
            to_run.func_globals[varname] = eval(varname)
        for name, value in self.global_closure.iteritems():
            to_run.func_globals[name] = value
        return to_run

PACKAGEDFUNCTIONSOURCE = '\n' + src.getsource(PackagedFunction)
