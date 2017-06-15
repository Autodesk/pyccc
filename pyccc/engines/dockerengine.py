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
from past.builtins import basestring

import subprocess

import docker
from pyccc import docker_utils as du, DockerMachineError
from pyccc import utils, files
from . import EngineBase, status


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

        if not hasattr(job, 'workingdir'):
            job.workingdir = self.default_wdir
        job.imageid = du.create_provisioned_image(self.client, job.image,
                                                  job.workingdir, job.inputs)
        cmdstring = "sh -c '%s'" % job.command

        job.container = self.client.create_container(job.imageid,
                                                     command=cmdstring,
                                                     working_dir=job.workingdir)
        self.client.start(job.container)
        job.containerid = job.container['Id']
        job.jobid = job.containerid


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
        return (utils.autodecode(stdout),
                utils.autodecode(stderr))




class DockerMachine(Docker):
    """ Convenience class for connecting to a docker machine.
    """
    def __init__(self, machinename):
        self.machinename = machinename
        client = du.docker_machine_client(machine_name=machinename)

        machstat = subprocess.check_output(['docker-machine', 'status', machinename]).strip()
        if machstat != 'Running':
            raise DockerMachineError('WARNING: docker-machine %s returned status: "%s"' %
                                     (machinename, status))

        super(DockerMachine, self).__init__(client)

    def __str__(self):
        return "%s engine on '%s' at %s" % (type(self).__name__, self.machinename,
                                            self.hostname)
