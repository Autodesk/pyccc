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
import json
import logging
import os
import subprocess

import io
import tarfile
from StringIO import StringIO


def create_provisioned_image(client, image, wdir, inputs, pull=False):
    build_context = create_build_context(image, inputs, wdir)
    tarobj = make_tar_stream(build_context)
    imageid = build_dfile_stream(client, tarobj, is_tar=True, pull=pull)
    return imageid


def create_build_context(image, inputs, wdir):
    """
    Creates a tar archive with a dockerfile and a directory called "inputs"
    The Dockerfile will copy the "inputs" directory to the chosen working directory
    """
    dockerstring = "FROM %s" % image

    build_context = {}
    if inputs:
        dockerstring += "\nCOPY inputs %s\n" % wdir
        for name, obj in inputs.iteritems():
            build_context['inputs/%s' % name] = obj
    else:
        dockerstring += "\nRUN mkdir -p %s\n" % wdir

    build_context['Dockerfile'] = StringIO(dockerstring)

    return build_context


def build_dfile_stream(client, dfilestream, is_tar=False, **kwargs):
    buildcmd = client.build(fileobj=dfilestream,
                            rm=True,
                            custom_context=is_tar,
                            **kwargs)

    # this blocks until the image is done building
    for x in buildcmd: logging.info('building image:%s' % (x.rstrip('\n')))

    result = json.loads(x)
    try:
        reply = result['stream']
    except KeyError:
        raise IOError(result)

    if reply.split()[:2] != 'Successfully built'.split():
        raise IOError('Failed to build image:%s'%reply)

    imageid = reply.split()[2]
    return imageid


def make_tar_stream(sdict):
    """
    Given a dictionary of the form {'filename':'file-like-object'},
    creates a tar stream with the _contents.
    TODO: don't do this in memory
    :return: TarFile stream (file-like object)
    """
    tarbuffer = io.BytesIO()
    tf = tarfile.TarFile(fileobj=tarbuffer, mode='w')
    for name, fileobj in sdict.iteritems():
        tar_add_string(tf, name, fileobj.read())
    tf.close()
    tarbuffer.seek(0)
    return tarbuffer


def tar_add_string(tf, filename, string):
    # This one function has given me a huge amount of trouble around formatting unicode strings.
    # The only real solution is to have everything in bytes by the time it gets here - no unicode
    #    objects allowed.
    # Some notes:
    # 1. the io module is python 3 centric, so io.BytesIO=str and io.StringIO=unicode
    # 2. If we just have a unicode string, there's NO WAY to determine what encoding is expected.
    # 3. The TarFile.addfile method appears to require a str (i.e., BytesIO) buffer. Everything
    #    needs to be encoded as bytes, not unicode, before we tar it up
    buff = io.BytesIO(string)
    tarinfo = tarfile.TarInfo(filename)
    tarinfo.size = len(string)
    tf.addfile(tarinfo, buff)


def docker_machine_env(machine_name):
    stdout = subprocess.check_output(['docker-machine', 'env', machine_name])
    vars = {}
    for line in stdout.split('\n'):
        fields = line.split()
        if len(line) < 1 or fields[0] != 'export': continue
        k, v = fields[1].split('=')
        vars[k] = v.strip('"')

    return vars


def docker_machine_client(machine_name='default'):
    import docker, docker.utils

    env = docker_machine_env(machine_name)
    os.environ.update(env)
    client = docker.Client(**docker.utils.kwargs_from_env(assert_hostname=False))

    return client


def kwargs_from_client(client, assert_hostname=False):
    """
    More or less stolen from docker-py's kwargs_from_env
    https://github.com/docker/docker-py/blob/c0ec5512ae7ab90f7fac690064e37181186b1928/docker/utils/utils.py
    :type client : docker.Client
    """
    from docker import tls
    if client.base_url == 'http+docker://localunixsocket':
        return {'base_url': 'unix://var/run/docker.sock'}

    params = {'base_url': client.base_url}
    if client.cert:
        # TODO: problem - client.cert is filepaths, and it would be insecure to send those files.
        params['tls'] = tls.TLSConfig(
            client_cert=client.cert,
            ca_cert=client.verify,
            verify=bool(client.verify),
            assert_hostname=assert_hostname)

    return params