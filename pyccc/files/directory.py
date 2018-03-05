# Copyright 2016-2018 Autodesk Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#s
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import os
import tarfile
import shutil

from .remotefiles import LazyDockerCopy
from . import get_target_path


class DirectoryReference(object):
    pass


class LocalDirectoryReference(DirectoryReference):
    """ This is a reference to a specific directory on the local filesystem.

    This allows entire directories to be staged into the dockerfile as input
    """
    def __init__(self, localpath):
        self.localpath = localpath

    def put(self, destination):
        """ Copy the referenced directory to this path

        The semantics of this command are similar to unix ``cp``: if ``destination``  already
        exists, the copied directory will be put at ``[destination] // [basename(localpath)]``. If
        it does not already exist, the directory will be renamed to this path (the parent directory
        must exist).

        Args:
            destination (str): path to put this directory
        """
        target = get_target_path(destination, self.localpath)
        shutil.copytree(self.localpath, target)


class DirectoryArchive(DirectoryReference):
    """A tar (or tar.gz) archive of a directory

    All files in this directory must be under a directory named "dirname". No other files
    will be expanded

    Args:
        archive_path (str): path to the existing archive
        dirname (str): name that this directory reference expands to (this is not checked!)
    """
    def __init__(self, archive_path, dirname):
        self.archive_path = archive_path
        self.dirname = dirname

    def put(self, destination):
        """ Copy the referenced directory to this path

        Note:
            This ignores anything not in the desired directory, given by ``self.dirname``.

        Args:
            destination (str): path to put this directory (which must NOT already exist)

        References:
            https://stackoverflow.com/a/8261083/1958900
        """
        target = get_target_path(destination, self.dirname)
        valid_paths = (self.dirname, './%s' % self.dirname)

        with tarfile.open(self.archive_path, 'r:*') as tf:
            members = []
            for tarinfo in tf:
                # Get only files under the directory `self.dirname`
                pathsplit = os.path.split(tarinfo.path)
                if pathsplit[0] not in valid_paths:
                    print('WARNING: skipped file "%s" in archive; not in directory "%s"' %
                          (tarinfo.path, self.dirname))
                    continue
                tarinfo.name = os.path.join(*pathsplit[1:])
                members.append(tarinfo)

            if not members:
                raise ValueError("No files under path directory '%s' in this tarfile")

            tf.extractall(target, members)


class DockerArchive(DirectoryArchive, LazyDockerCopy):
    """
    Reference to an archived directory from a docker container.

    Notes:
     - This is currently a bit of a frankenclass
     - Because it requires access to a docker daemon, this object is not particularly portable.
    """
    def __init__(self, *args, **kwargs):
        LazyDockerCopy.__init__(self, *args, **kwargs)
        self.archive_path = None
        self.dirname = self.basename

    def put(self, destination):
        """ Copy the referenced directory to this path

        Args:
            destination (str): path to put this directory (which must NOT already exist)
        """
        if not self._fetched:
            self._fetch()
        DirectoryArchive.put(self, destination)

    put.__doc__ = DirectoryArchive.put.__doc__

    def _fetch(self):
        self.archive_path = self._open_tmpfile()
        stream = self._get_tarstream()
        shutil.copyfileobj(stream, self.tmpfile)
        stream.close()
        self.tmpfile.close()
