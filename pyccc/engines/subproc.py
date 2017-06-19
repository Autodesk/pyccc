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

import os
import subprocess
import locale

from pyccc import utils as utils, files
from . import EngineBase, status


class Subprocess(EngineBase):
    """Just runs a job locally in a subprocess.
    For now, don't return anything until job completes"""

    hostname = 'local'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.term_encoding = locale.getpreferredencoding()

    def get_status(self, job):
        if job.subproc.poll() is None:
            return status.RUNNING
        else:
            return status.FINISHED

    def test_connection(self):
        job = self.launch(command='echo check12')
        job.wait()
        if job.stdout.strip() != 'check12':
            raise

    def get_engine_description(self, job):
        """
        Return a text description for the UI
        """
        return 'Local subprocess %s' % job.subproc.pid

    def launch(self, image=None, command=None,  **kwargs):
        if command is None:
            command = image
        return super(Subprocess, self).launch('no_image', command, **kwargs)

    def submit(self, job):
        self._check_job(job)
        job.workingdir = utils.make_local_temp_dir()
        if job.inputs:
            for filename, f in job.inputs.items():
                f.put(os.path.join(job.workingdir, filename))

        job.subproc = subprocess.Popen(job.command,
                                       shell=True,
                                       cwd=job.workingdir,
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE,
                                       env={'PYTHONIOENCODING': 'utf-8'})
        job.jobid = job.subproc.pid
        job._started = True
        return job.subproc.pid

    def kill(self, job):
        job.subproc.terminate()

    def wait(self, job):
        return job.subproc.wait()

    def _list_output_files(self, job, dir=None):
        if dir is None: dir = job.workingdir
        filenames = {}
        for fname in os.listdir(dir):
            abs_path = '%s/%s' % (dir, fname)
            if os.path.islink(dir):
                continue
            elif os.path.isdir(fname):
                dirfiles = self._list_output_files(job, dir=abs_path)
                filenames.update({'%s/%s' % (fname, f): obj
                                  for f, obj in dirfiles.items()})
            else:
                filenames[fname] = files.LocalFile(abs_path)
        return filenames

    def _get_final_stds(self, job):
        strings = []
        for fileobj in (job.subproc.stdout, job.subproc.stderr):
            strings.append(fileobj.read().decode('utf-8'))
        return strings
