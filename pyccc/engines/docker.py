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
import docker
from pyccc import docker_utils as du
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
        self._check_job(job)

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
        job.jobid = job.containerid

    def wait(self, job):
        self.client.wait(job.container)

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
        return (self.client.logs(job.container, stdout=True, stderr=False),
                self.client.logs(job.container, stdout=False, stderr=True))

    def __getstate__(self):
        """
        We don't pickle the docker client, for now
        """
        newdict = self.__dict__.copy()
        newdict.pop('client', None)
        return newdict


class DockerMachine(Docker):
    """ Convenience class for connecting to a docker machine.
    """
    def __init__(self, machine_name):
        client = du.docker_machine_client(machine_name=machine_name)
        super(DockerMachine, self).__init__(client)