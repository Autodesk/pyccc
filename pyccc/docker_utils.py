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

import json
import logging
import os
import subprocess
import io
import tarfile
import tempfile
import gzip

import pyccc

from .exceptions import DockerMachineError
from . import files


def create_provisioned_image(client, image, wdir, inputs, pull=False):
    build_context = create_build_context(image, inputs, wdir)
    with tempfile.NamedTemporaryFile(suffix='.tar.gz', mode='wb') as tfile:
        gzstream = gzip.GzipFile(fileobj=tfile, mode='wb')
        make_tar_stream(build_context, gzstream)
        gzstream.flush()
        tfile.flush()
        imageid = build_dfile_stream(client, tfile.name, pull=pull)
    return imageid


def create_build_context(image, inputs, wdir):
    """
    Creates a tar archive with a dockerfile and a directory called "inputs"
    The Dockerfile will copy the "inputs" directory to the chosen working directory
    """
    assert os.path.isabs(wdir)

    dockerlines = ["FROM %s" % image,
                    "RUN mkdir -p %s" % wdir]
    build_context = {}

    # This loop creates a Build Context for building the provisioned image
    # Each input file is assigned a unique name, in preparation for creating a tar archive
    if inputs:
        for ifile, (path, obj) in enumerate(inputs.items()):
            src = os.path.basename(path) + '-%s' % ifile  # mangling to ensure uniqueness
            if os.path.isabs(path):
                dest = path
            else:
                dest = os.path.join(wdir, path)
            dockerlines.append('ADD %s %s' % (src, dest))
            build_context[src] = obj

    dockerstring = '\n'.join(dockerlines)
    build_context['Dockerfile'] = pyccc.BytesContainer(dockerstring.encode('utf-8'))
    return build_context


def build_dfile_stream(client, dfilepath, **kwargs):
    # dfilepath is the path to the already .tgz-archived build context

    with open(dfilepath, 'rb') as dfilestream:
        buildcmd = client.build(fileobj=dfilestream,
                                rm=True,
                                custom_context=True,
                                encoding='gzip',
                                **kwargs)

    # this blocks until the image is done building
    for x in buildcmd:
        if isinstance(x, bytes):
            x = x.decode('utf-8')
        logging.info('building image:%s' % (x.rstrip('\n')))

    result = json.loads(_issue1134_helper(x))
    try:
        reply = result['stream']
    except KeyError:
        raise IOError(result)

    if reply.split()[:2] != 'Successfully built'.split():
        raise IOError('Failed to build image:%s' % reply)

    imageid = reply.split()[2]
    return imageid


def _issue1134_helper(x):
    # workaround for https://github.com/docker/docker-py/issues/1134
    # docker appears to return two JSONs in a single string. This parses the string to return the
    # last JSON object only
    s = x.strip()
    assert s[0] == '{'
    num_brace = 1
    rootbrace = 0

    for ichar in range(1,len(s)):
        char = s[ichar]
        if char == '}' and s[ichar-1] != '\\':
            num_brace -= 1
            if num_brace == 0:
                endbrace = ichar

        elif char == '{' and s[ichar-1] != '\\':
            num_brace += 1
            if num_brace == 1:
                rootbrace = ichar

    return s[rootbrace: endbrace+1]


def make_tar_stream(build_context, buffer):
    """ Write a tar stream of the build context to the provided buffer

    Args:
        build_context (Mapping[str, pyccc.FileReferenceBase]): dict mapping filenames to file references
        buffer (io.BytesIO): writable binary mode buffer
    """
    tf = tarfile.TarFile(fileobj=buffer, mode='w')
    for context_path, fileobj in build_context.items():
        if getattr(fileobj, 'localpath', None) is not None:
            tf.add(fileobj.localpath, arcname=context_path)
        else:
            tar_add_bytes(tf, context_path, fileobj.read('rb'))
    tf.close()


def tar_add_bytes(tf, filename, bytestring):
    """ Add a file to a tar archive

    Args:
        tf (tarfile.TarFile): tarfile to add the file to
        filename (str): path within the tar file
        bytestring (bytes or str): file contents. Must be :class:`bytes` or
            ascii-encodable :class:`str`
    """
    if not isinstance(bytestring, bytes):  # it hasn't been encoded yet
        bytestring = bytestring.encode('ascii')
    buff = io.BytesIO(bytestring)
    tarinfo = tarfile.TarInfo(filename)
    tarinfo.size = len(bytestring)
    tf.addfile(tarinfo, buff)


def docker_machine_env(machine_name):
    try:
        stdout = subprocess.check_output(['docker-machine', 'env', machine_name])
    except (subprocess.CalledProcessError, OSError):
        raise DockerMachineError('Could not find docker-machine "%s"' % machine_name)

    vars = {}
    for line in stdout.split('\n'):
        fields = line.split()
        if len(line) < 1 or fields[0] != 'export':
            continue
        k, v = fields[1].split('=')
        vars[k] = v.strip('"')

    return vars


def docker_machine_client(machine_name='default'):
    import docker.utils

    env = docker_machine_env(machine_name)
    os.environ.update(env)
    client = get_docker_apiclient(**docker.utils.kwargs_from_env(assert_hostname=False))

    return client


def get_docker_apiclient(*args, **kwargs):
    import docker

    if hasattr(docker, 'APIClient'):
        ClientClass = docker.APIClient
    else:
        ClientClass = docker.Client
    return ClientClass(*args, **kwargs)


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