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
import time

from pyccc import files, status
from . import EngineBase

class TimeoutError(Exception): pass

class CloudComputeCannon(EngineBase):

    # translate CCC commands into
    STATUSES = {'pending': status.QUEUED,
                'copying_image': status.DOWNLOADING,
                'container_running': status.RUNNING,
                'finished_working': status.RUNNING,
                'copying_logs': status.FINISHING,
                'finished': status.FINISHED,
                'cancelled': status.KILLED,
                'failed': status.ERROR
                }

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

        if '://' not in url: url = 'http://' + url
        if not url.endswith('/'): url += '/'
        self.base_url = url
        self.endpoint = url + 'api/rpc'
        self.proxy = JsonRpcProxy(self.endpoint)
        self.hostname = self.base_url

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
        self._check_job(job)

        cmdstring = ['CCC_WORKDIR_=`pwd`']

        if job.inputs:
            cmdstring = ['cp /inputs * .'] + cmdstring

        if isinstance(job.command, basestring):
            cmdstring.append(job.command)
        else:
            cmdstring.append(' '.join(job.command))

        cmdstring.append('cd $CCC_WORKDIR && cp -r * /outputs 2>/dev/null')

        returnval = self.proxy.submitjob(image=job.image,
                                         command=['sh', '-c', ' && '.join(cmdstring)],
                                         inputs=job.inputs,
                                         cpus=job.numcpus,  # how is this the "minimum"?
                                         maxDuration=1000*job.runtime,
                                         workDir='/workingdir')

        job.jobid = returnval['jobId']
        job._result_json = None

    def get_status(self, job):
        response = self.proxy.job(command='status', jobId=[job.jobid])
        stat = self.STATUSES[response[job.jobid]]
        return stat

    def wait(self, job):
        # TODO: don't poll!
        polltime = 1  # start out polling every second
        wait_time = 0
        run_time = 0
        while job.status not in status.DONE_STATES:
            time.sleep(polltime)
            wait_time += polltime
            if job.status == status.RUNNING:
                run_time += polltime
            if run_time > job.runtime:
                raise TimeoutError('Job timed out - status "%s"' % job.status)
            if wait_time > 1000: polltime = 60
            elif wait_time > 100: polltime = 20
            elif wait_time > 10: polltime = 5


    def _get_result_json(self, job):
        if job._result_json is None:
            job._result_json = self.proxy.job(command='result',
                                              jobId=[job.jobid])
        return job._result_json[job.jobid]

    def _download(self, path):
        url = self.base_url + path
        return files.HttpContainer(url)

    def _get_final_stds(self, job):
        result_json = self._get_result_json(job)
        stdout = self._download(result_json['stdout']).read()
        stderr = self._download(result_json['stderr']).read()
        return stdout, stderr

    def _list_output_files(self, job):
        results = self._get_result_json(job)
        output_files = {fname: files.HttpContainer(results['outputsBaseUrl']+'/'+fname)
                        for fname in results['outputs']}
        return output_files
