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
from __future__ import print_function, unicode_literals, absolute_import, division
from future import standard_library
standard_library.install_aliases()
from future.builtins import *

from pyccc import PythonCall, PythonJob, Job


class EngineBase(object):
    """ This is the base class for compute engines - the environments that actually run the jobs.

    This class defines the implementation only - you intantiate one of its subclasses
    """

    hostname = 'not specified'  # this should be overidden in subclass init methods

    def __call__(self, *args, **kwargs):
        pass

    @property
    def name(self):
        """ str: same as str(self) (for backwards compatibility)
        """
        return str(self)

    def __str__(self):
        return '%s engine on host: %s' % (type(self).__name__, self.hostname)

    def __repr__(self):
        try:
            return '<%s>' % str(self)
        except:
            return '<%s engine at %s (custom __repr__ failed)>' % (
                type(self).__name__, hex(id(self)))

    def launch(self, image, command, **kwargs):
        """
        Create a job on this engine

        Args:
            image (str): name of the docker image to launch
            command (str): shell command to run
        """
        if isinstance(command, PythonCall):
            return PythonJob(self, image, command, **kwargs)
        else:
            return Job(self, image, command, **kwargs)

    def submit(self, job):
        """
        submit job to engine
        """
        raise NotImplementedError()

    def _check_job(self, job):
        job.engine = self

    def wait(self, job):
        """
        block until job completes
        """
        raise NotImplementedError()

    def kill(self, job):
        """
        Remove job from queue or terminate it
        """
        raise NotImplementedError()

    def get_status(self, job):
        """
        Return a valid job status value from pyccc.status
        """
        raise NotImplementedError()

    def get_stdoutstream(self, job):
        """
        Return a stream for the stdout
        """
        raise NotImplementedError()

    def get_stderrstream(self, job):
        """
        Return a stream for the stderr
        """
        raise NotImplementedError()

    def get_outputstream(self, job):
        """
        Return a stream for the specified output file
        """
        raise NotImplementedError()

    def _list_output_files(self, job):
        """
        Recursively list all changed files under working directory.
        To be called only after job has finished.
        :return: dict of filenames and CBS file objects
        """
        raise NotImplementedError()

    def _get_final_stds(self, job):
        """
        To be called only after job has finished
        :return: (final stdout, final stderr)
        """
        raise NotImplementedError()