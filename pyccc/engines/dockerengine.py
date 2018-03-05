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

import docker
from .. import docker_utils as du, DockerMachineError
from .. import utils, files, status
from . import EngineBase


class Docker(EngineBase):
    """ A compute engine - uses a docker server to run jobs
    """
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

        job.container = self.client.create_container(job.imageid, **container_args)
        self.client.start(job.container)
        job.containerid = job.container['Id']
        job.jobid = job.containerid

    def _generate_container_args(self, job):
        container_args = dict(command="sh -c '%s'" % job.command,
                              working_dir=job.workingdir,
                              environment={'PYTHONIOENCODING':'utf-8'})

        if job.engine_options:
            volumes = []
            binds = []

            # mount the docker socket into the container
            if job.engine_options.get('mount_docker_socket', False):
                volumes.append('/var/run/docker.sock')
                binds.append('/var/run/docker.sock:/var/run/docker.sock:rw')

            # handle other mounted volumes
            for volume, mount in job.engine_options.get('volumes', {}).items():
                if isinstance(mount, (list, tuple)):
                    mountpoint, mode = mount
                    bind = '%s:%s:%s' % (volume, mountpoint, mode)
                else:
                    mountpoint = mount
                    mode = None
                    bind = '%s:%s' % (volume, mountpoint)

                volumes.append(mountpoint)
                binds.append(bind)

            if volumes or binds:
                container_args['volumes'] = volumes
                container_args['host_config'] = self.client.create_host_config(binds=binds)

        return container_args

    def wait(self, job):
        return self.client.wait(job.container)

    def kill(self, job):
        self.client.kill(job.container)

    def get_status(self, job):
        inspect = self.client.inspect_container(job.containerid)
        if inspect['State']['Running']:
            return status.RUNNING
        else:
            return status.FINISHED

    def get_directory(self, job, path):
        docker_host = du.kwargs_from_client(self.client)
        remotedir = files.DockerArchive(docker_host, job.containerid, path)
        return remotedir

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
        stdout = self.client.logs(job.container, stdout=True, stderr=False)
        stderr = self.client.logs(job.container, stdout=False, stderr=True)
        return stdout.decode('utf-8'), stderr.decode('utf-8')
