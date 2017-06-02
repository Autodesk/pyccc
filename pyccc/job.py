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
Low-level API functions. These are the actual REST interactions with the workflow server.
"""
from __future__ import print_function, unicode_literals, absolute_import, division
from future import standard_library
standard_library.install_aliases()
from future.builtins import *
from past.builtins import basestring

import fnmatch

import pyccc
from pyccc import files, status
from pyccc.utils import *


def exports(o):
    __all__.append(o.__name__)
    return o
__all__ = []


class EngineFunction(object):
    """
    Allows you to call
    job.engine.function_name(job) by just calling
    job.function_name()
    """
    def __init__(self, function_name):
        self.name = function_name

    def __get__(self, obj, owner):
        func = getattr(obj.engine, self.name)
        return lambda: func(obj)


@exports
class Job(object):
    """ Specification for a computational job.

    This class is mainly a data container that can interact with the computational engines.

    Args:
        engine (pycc.engines.EngineBase): compute engine
        image (str): docker image to use
        command (str): command to run in the docker image
        name (str): name of this job (optional)
        submit (bool): submit job to engine immediately (default: True if engine and image are
            both supplied, False otherwise)
        inputs (Mapping[str,files.FileContainer]): dict containing input file names and their
            contents (which can be either a FileContainer or just a string)
        on_status_update (callable): function that can be called as ``func(job)``; will be called
            locally whenever the job's status field is updated
        when_finished (callable): function that can be called as ``func(job)``; will be called
            locally once, when this job completes
        numcpus (int): number of CPUs required (default:1)
        runtime (int): kill job if the runtime exceeds this value (in seconds) (default: 1 hour)`
    """
    def __init__(self, engine=None,
                 image=None,
                 command=None,
                 name='untitled',
                 submit=True,
                 inputs=None,
                 requirements=None,
                 numcpus=1,
                 runtime=3600,
                 on_status_update=None,
                 when_finished=None):

        self.name = name
        self.engine = engine
        self.image = image
        self.command = if_not_none(command, '')

        self.inputs = inputs
        if self.inputs is not None:  # translate strings into file objects
            for filename, fileobj in inputs.items():
                if isinstance(fileobj, basestring):
                    self.inputs[filename] = files.StringContainer(fileobj)
                else:
                    self.inputs[filename] = fileobj

        self.requirements = if_not_none(requirements, {})
        self.on_status_update = on_status_update
        self.when_finished = when_finished
        self.numcpus = numcpus
        self.runtime = runtime

        self._reset()

        if submit and self.engine and self.image:
            self.submit()

    def _reset(self):
        self._submitted = False
        self._started = False
        self._final_stdout = None
        self._final_stderr = None
        self._finished = False
        self._callback_result = None
        self._output_files = None
        self.jobid = None
        self._stopped = None

    kill = EngineFunction('kill')
    get_stdout_stream = EngineFunction('get_stdoutstream')
    get_stderr_stream = EngineFunction('get_stdoutstream')
    get_engine_description = EngineFunction('get_engine_description')
    _get_final_stds = EngineFunction('_get_final_stds')
    _list_output_files = EngineFunction('_list_output_files')

    def __str__(self):
        desc = ['Job "%s" status:%s' % (self.name, self.status)]
        if self.jobid: desc.append('jobid:%s' % self.jobid)
        if self.engine: desc.append('engine:%s' % type(self.engine).__name__)
        return ' '.join(desc)

    def __repr__(self):
        s = str(self)
        if self.engine:
            s += ' host:%s' % self.engine.hostname
        if not self.jobid:
            s += ' at %s' % hex(id(self))
        return '<%s>' % s

    def __getstate__(self):
        state = self.__dict__.copy()
        state.pop('subproc', None)
        return state

    def submit(self, wait=False, resubmit=False):
        """ Submit this job to the assigned engine.

        Args:
            wait (bool): wait until the job completes?
            resubmit (bool): clear all job info and resubmit the job?

        Raises:
            ValueError: If the job has been previously submitted (and resubmit=False)
        """
        if self._submitted:
            if resubmit:
                self._reset()
            else:
                raise ValueError('This job has already been submitted')

        self.engine.submit(self)
        self._submitted = True
        if wait: self.wait()

    def wait(self):
        """Wait for job to finish"""
        returncode = self.engine.wait(self)
        if not self._finished:
            self._finish_job()
        return returncode

    @property
    def exitcode(self):
        if not self._finished:
            raise pyccc.JobStillRunning(self)
        return self.wait()

    @property
    def status(self):
        """
        Returns status of 'queued', 'running', 'finished' or 'error'
        """
        if self._stopped:
            return self._stopped
        elif self.jobid:
            stat = self.engine.get_status(self)
            if stat in status.DONE_STATES:
                self._stopped = stat
            return stat
        else:
            return "Unsubmitted"

    def _finish_job(self):
        """
        To be called after job has finished.
        Retreives stdout, stderr, and list of available files
        :return:
        """
        if self._finished: return
        stat = self.status
        if stat not in status.DONE_STATES:
            raise pyccc.JobStillRunning(self)
        if stat != status.FINISHED:
            raise pyccc.JobErrorState(self, 'Job did not complete successfully (status:%s)'%
                                      stat)
        self._output_files = self.engine._list_output_files(self)
        self._final_stdout, self._final_stderr = self.engine._get_final_stds(self)
        self._finished = True
        if self.when_finished is not None:
            self._callback_result = self.when_finished(self)

    @property
    def result(self):
        """
        Returns:
            Result of the callback function, if present, otherwise none.
        """
        if not self._finished: self._finish_job()
        return self._callback_result

    @property
    def stdout(self):
        if not self._finished: self._finish_job()
        return self._final_stdout

    @property
    def stderr(self):
        if not self._finished: self._finish_job()
        return self._final_stderr

    def get_output(self, filename=None):
        """
        Return abstract file references to complete files
        - returns a dict if filename is None,
        or just the specific file otherwise
        """
        if not self._finished: self._finish_job()
        if filename: return self._output_files[filename]
        else: return self._output_files

    def glob_output(self, pattern):
        """ Return dict of all files that match the glob pattern
        """
        filenames = self.get_output()
        matches = fnmatch.filter(filenames.keys(), pattern)
        return {f:filenames[f] for f in matches}

    def get_display_object(self):
        """Return a jupyter widget"""
        from .ui import JobStatusDisplay, widgets_enabled
        if widgets_enabled:
            return JobStatusDisplay(self)
        else:
            return 'Job "%s" launched. id:%s' % (self.name, self.jobid)
