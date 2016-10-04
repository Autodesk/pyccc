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


class JobExceptionBase(Exception):
    def __init__(self, job, msg=None):
        self.job = job
        self.msg = msg


class ProgramFailure(Exception):
    pass


class TimeoutError(JobExceptionBase):
    """ This job's status is not "Finshed" or "Error"
    """


class JobStillRunning(JobExceptionBase):
    """ Raised when a job's status is not "Finshed" or "Error"
    """

class JobErrorState(JobExceptionBase):
    """ For jobs that have halted but did not complete successfully
    """


class EngineTestError(Exception):
    """ Raised when an engine fails basic connection tests

    Args:
        engine (pyccc.engines.base.EngineBase): the little engine that couldn't
    """
    def __init__(self, engine):
        super(EngineTestError, self).__init__('Failed to run jobs on Engine: %s' % engine)


class DockerMachineError(Exception):
    """ Failures related to connecting to docker machines
    """