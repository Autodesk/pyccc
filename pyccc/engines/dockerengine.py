# Copyright 2016-2018 Autodesk Inc.
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
from past.builtins import basestring

import subprocess

import docker.errors

from .. import docker_utils as du, DockerMachineError
from .. import utils, files, status, exceptions
from . import EngineBase

CTR_MODIFIED = 0
CTR_ADDED = 1
CTR_DELETED = 2


class Docker(EngineBase):
    """ A compute engine - uses a docker server to run jobs
    """
    USES_IMAGES = True
    ABSPATHS = True

    def __init__(self, client=None, workingdir='/workingdir'):
        """ Initialization:

        Args:
            client (docker.Client): a docker-py client. If not passed, we will try to create the
                client from the job's environmental varaibles
            workingdir (str): default working directory to create in the containers
        """

        self.client = self.connect_to_docker(client)
        self.default_wdir = workingdir
        self.hostname = self.client.base_url

    def connect_to_docker(self, client=None):
        if isinstance(client, basestring):
            client = du.get_docker_apiclient(client)
        if client is None:
            client = du.get_docker_apiclient(**docker.utils.kwargs_from_env())
        return client

    def __getstate__(self):
        """
        We don't pickle the docker client, for now
        """
        newdict = self.__dict__.copy()
        if 'client' in newdict:
            newdict['client'] = None
        return newdict

    def test_connection(self):
        version = self.client.version()
        return version

    def get_job(self, jobid):
        """ Return a Job object for the requested job id.

        The returned object will be suitable for retrieving output, but depending on the engine,
        may not populate all fields used at launch time (such as `job.inputs`, `job.commands`, etc.)

        Args:
            jobid (str): container id

        Returns:
            pyccc.job.Job: job object for this container

        Raises:
            pyccc.exceptions.JobNotFound: if no job could be located for this jobid
        """
        import shlex
        from pyccc.job import Job

        job = Job(engine=self)
        job.jobid = job.rundata.containerid = jobid
        try:
            jobdata = self.client.inspect_container(job.jobid)
        except docker.errors.NotFound:
            raise exceptions.JobNotFound(
                    'The daemon could not find containter "%s"' % job.jobid)

        cmd = jobdata['Config']['Cmd']
        entrypoint = jobdata['Config']['Entrypoint']

        if len(cmd) == 3 and cmd[0:2] == ['sh', '-c']:
            cmd = cmd[2]
        elif entrypoint is not None:
            cmd = entrypoint + cmd

        if isinstance(cmd, list):
            cmd = ' '.join(shlex.quote(x) for x in cmd)

        job.command = cmd
        job.env = jobdata['Config']['Env']
        job.workingdir = jobdata['Config']['WorkingDir']
        job.rundata.container = jobdata

        return job


    def submit(self, job):
        """ Submit job to the engine

        Args:
            job (pyccc.job.Job): Job to submit
        """
        self._check_job(job)

        if job.workingdir is None:
            job.workingdir = self.default_wdir
        job.imageid = du.create_provisioned_image(self.client, job.image,
                                                  job.workingdir, job.inputs)

        container_args = self._generate_container_args(job)

        job.rundata.container = self.client.create_container(job.imageid, **container_args)
        self.client.start(job.rundata.container)
        job.rundata.containerid = job.rundata.container['Id']
        job.jobid = job.rundata.containerid

    def _generate_container_args(self, job):
        container_args = dict(command="sh -c '%s'" % job.command,
                              working_dir=job.workingdir,
                              environment={'PYTHONIOENCODING':'utf-8'})

        if job.env:
            container_args['environment'].update(job.env)

        volumes = []
        binds = []

        # mount the docker socket into the container (two ways to do this for backwards compat.)
        if job.withdocker or job.engine_options.get('mount_docker_socket', False):
            volumes.append('/var/run/docker.sock')
            binds.append('/var/run/docker.sock:/var/run/docker.sock:rw')

        # handle other mounted volumes
        for volume, mount in job.engine_options.get('volumes', {}).items():
            if isinstance(mount, (list, tuple)):
                mountpoint, mode = mount
                bind = '%s:%s:%s' % (volume, mountpoint, mode)
            else:
                mountpoint = mount
                bind = '%s:%s' % (volume, mountpoint)

            volumes.append(mountpoint)
            binds.append(bind)

        if volumes or binds:
            container_args['volumes'] = volumes
            container_args['host_config'] = self.client.create_host_config(binds=binds)

        return container_args

    def wait(self, job):
        stat = self.client.wait(job.rundata.container)
        if isinstance(stat, int):  # i.e., docker<3
            return stat
        else:  # i.e., docker>=3
            return stat['StatusCode']

    def kill(self, job):
        self.client.kill(job.rundata.container)

    def get_status(self, job):
        inspect = self.client.inspect_container(job.rundata.containerid)
        if inspect['State']['Running']:
            return status.RUNNING
        else:
            return status.FINISHED

    def get_directory(self, job, path):
        docker_host = du.kwargs_from_client(self.client)
        remotedir = files.DockerArchive(docker_host, job.rundata.containerid, path)
        return remotedir

    def _list_output_files(self, job):
        docker_diff = self.client.diff(job.rundata.container)
        if docker_diff is None:
            return {}

        changed_files = [f['Path'] for f in docker_diff
                         if f['Kind'] in (CTR_MODIFIED, CTR_ADDED)]
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

            remotefile = files.LazyDockerCopy(docker_host, job.rundata.containerid, filename)
            output_files[relative_path] = remotefile
        return output_files

    def _get_final_stds(self, job):
        stdout = self.client.logs(job.rundata.container, stdout=True, stderr=False)
        stderr = self.client.logs(job.rundata.container, stdout=False, stderr=True)
        return stdout.decode('utf-8'), stderr.decode('utf-8')
