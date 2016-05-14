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
import os
import subprocess
import functools

import requests
try: #docker-py is required only for the Docker class
    import docker
    import docker.utils
except ImportError:
    pass

from pyccc import files
import pyccc.docker_utils as du
import pyccc.utils as utils
from pyccc.job import Job
from pyccc.python import PythonJob, PythonCall


class EngineBase(object):
    """ This is the base class for compute engines - the environments that actually run the jobs.

    This class defines the implementation only - you intantiate one of its subclasses
    """

    def __call__(self, *args, **kwargs):
        pass

    def launch(self, image, command, **kwargs):
        """
        Create a job on this engine

        Args:
            image (str): name of the docker image to launch
            command (str): shell command to run
        """
        if issubclass(command.__class__,PythonCall):
            to_call = PythonJob
        else:
            to_call = Job
        return to_call(self, image, command, **kwargs)

    def get_engine_description(self, job):
        """
        Return a text description for the UI
        """
        return "Abstract base engine"

    def submit(self, job):
        """
        submit job to engine
        """
        raise NotImplementedError()

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


class CloudComputeCannon(EngineBase):
    def __reduce__(self):
        """Pickling helper - returns arguments to reinitialize this object"""
        return CloudComputeCannon, (self.host, False)

    def __init__(self, url, testconnection=True):
        """ Connect to the server

        Args:
            url (str): endpoint url, including protocol and port,
                e.g. ``http://ip.address.com:9000``
            testconnection (bool): test the connection immediately
            workingdir (str): default container location to use as working directory
        """
        from pyccc.jsonrpc import JsonRpcProxy

        self.host = url
        self.proxy = JsonRpcProxy(url)

        if testconnection: self.test_connection()

    def test_connection(self):
        """ Test that we can successfully talk to the server.

        Doesn't test that it can run jobs, however

        Raises:
            ValueError: if the server doesn't return a valid response
            AssertionError: the return value was unexpected

        Returns:
            bool: True (otherwise, raises exception)
        """
        result = self.proxy.test(echo='check12')
        assert result.strip() == 'check12check12'

    def get_engine_description(self, job):
        """ Return a text description of a job

        Args:
            job (pyccc.job.Job): Job to inspect

        Returns:
            str: text description
        """
        return 'Job ID %s on %s' % (job.jobid, self.host)

    def submit(self, job):
        # TODO: inherit docstring
        returnval = self.proxy.submitjob(image=job.image,
                                         command=job.command,
                                         cpus=job.numcpus,  # how is this the "minimum"?
                                         maxDuration=job.runtime)

        job.jobid = returnval['jobId']

    def get_status(self, job):
        # Pending|Working|Finalizing|Finished
        response = self.proxy.job(command='status', jobId=[job.jobid])
        return response[job.id]

    def wait(self, job):
        raise NotImplementedError()


class Subprocess(EngineBase):
    """Just runs a job locally in a subprocess.
    For now, don't return anything until job completes"""
    def get_status(self,job):
        if job.subproc.poll() is None: return 'running'
        else: return 'finished'

    def get_engine_description(self, job):
        """
        Return a text description for the UI
        """
        return 'Local subprocess %s' % job.subproc.pid

    def submit(self, job):
        job.workingdir = utils.make_local_temp_dir()
        for filename, file in job.inputs.iteritems():
            file.put('%s/%s' % (job.workingdir, filename))

        job.subproc = subprocess.Popen(job.command,
                                       shell=True,
                                       cwd=job.workingdir,
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE)
        job._started = True
        return job.subproc.pid

    def kill(self, job):
        job.subproc.terminate()

    def wait(self, job):
        job.subproc.wait()

    def _list_output_files(self, job, dir=None):
        if dir is None: dir = job.workingdir
        filenames = {}
        for fname in os.listdir(dir):
            abs_path = '%s/%s' % (dir, fname)
            if os.path.islink(dir):
                continue
            elif os.path.isdir(fname):
                dirfiles = job._list_output_files(dir=abs_path)
                filenames.update({'%s/%s' % (fname, f): obj
                                  for f, obj in dirfiles.iteritems()})
            else:
                filenames[fname] = files.LocalFile(abs_path)
        return filenames

    def _get_final_stds(self, job):
        strings = []
        #Todo - we'll need to buffer any streamed output, since stdout isn't seekable
        for fileobj in (job.subproc.stdout,job.subproc.stderr):
            strings.append(fileobj.read())
        return strings


class Docker(EngineBase):
    """ A compute engine - uses a docker server to run jobs
    """
    def __init__(self, client=None, workingdir='/default_wdir'):
        """ Initialization:

        Args:
            client (docker.Client): a docker-py client. If not passed, we will try to create the
                client from the job's environmental varaibles
            workingdir (str): default working directory to create in the containers
        """
        if client is None:
            client = docker.Client(**docker.utils.kwargs_from_env())
        self.client = client
        self.default_wdir = workingdir
        self.hostname = self.client.base_url

    def get_engine_description(self, job):
        """ Return a text description of a job

        Args:
            job (pyccc.job.Job): Job to inspect

        Returns:
            str: text description
        """
        return 'Docker host %s, container: %s' % (self.hostname, job.containerid[:12])

    def submit(self, job):
        """ Submit job to the engine

        Args:
            job (pyccc.job.Job): Job to submit
        """
        if not hasattr(job, 'workingdir'):
            job.workingdir = self.default_wdir
        job.imageid = du.create_provisioned_image(self.client, job.image,
                                                  job.workingdir, job.inputs)
        cmdstring = "bash -c '%s'" % job.command

        job.container = self.client.create_container(job.imageid,
                                                     command=cmdstring,
                                                     working_dir=job.workingdir)
        self.client.start(job.container)
        job.containerid = job.container['Id']

    def wait(self, job):
        self.client.wait(job.container)

    def kill(self, job):
        self.client.kill(job.container)

    def get_status(self, job):
        inspect = self.client.inspect_container(job.containerid)
        if inspect['State']['Running']:
            return 'running'
        else:
            return 'finished'

    def _list_output_files(self, job):
        docker_diff = self.client.diff(job.container)
        if docker_diff is None:
            return {}

        changed_files = [f['Path'] for f in docker_diff]
        file_paths = utils.remove_directories(changed_files)
        docker_host = du.kwargs_from_client(self.client)

        output_files = {}
        for filename in file_paths:
            # Return relative localpath unless it's not under the working directory
            if filename.strip()[0] != '/':
                relative_path = '%s/%s' % (job.workingdir, filename)
            elif filename.startswith(job.workingdir):
                relative_path = filename[len(job.workingdir):]
                if len(relative_path) > 0 and relative_path[0] == '/':
                    relative_path = relative_path[1:]
            else:
                relative_path = filename

            remotefile = files.LazyDockerCopy(docker_host, job.containerid, filename)
            output_files[relative_path] = remotefile
        return output_files

    def _get_final_stds(self, job):
        return (self.client.logs(job.container, stdout=True, stderr=False),
                self.client.logs(job.container, stdout=False, stderr=True))

    def __getstate__(self):
        """
        We don't pickle the docker client, for now
        """
        newdict = self.__dict__.copy()
        newdict.pop('client', None)
        return newdict
