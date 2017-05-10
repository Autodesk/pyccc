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
import shutil
import socket

from . import BytesContainer, StringContainer, get_tempfile


class FileContainer(BytesContainer):
    """ In-memory file reference.

    Args:
        filename (str): name of the file to read
        encoded_with (str): encoding of the file (default: system default)
    """
    def __init__(self, filename, encoded_with=None):
        with open(filename, 'rb') as infile:
            contents = infile.read()
        super().__init__(contents, encoded_with=encoded_with, name=filename)

        self.source = filename
        self.sourcetype = '%s' % socket.gethostname()
        self.localpath = None

    def __str__(self):
        return 'In-memory file from %s: %s (%d chars)' % (self.sourcetype, self.source, len(self._contents))

    def __repr__(self):
        return '<%s>' % self.__str__()


class LocalFile(FileContainer):
    """ A reference to a local file.

    Note:
         This class is not designed to work with files that will be moved or edited.

    Args:
        path (str): path to file
        check_exists (bool): make sure the file exists when this object is created
    """

    def __reduce__(self):
        return StringContainer, (self.read(),)

    def __init__(self, path, encoded_with=None, check_exists=True):
        if check_exists and not os.path.exists(path):
            raise IOError('File not found: %s' % path)

        self.source = path
        self.localpath = self.source
        self.sourcetype = 'Local file on %s' % socket.gethostname()
        self.encoded_with = encoded_with

    def put(self, filename, encoding=None):
        if encoding is not None:
            raise ValueError('Cannot encode as %s - this file is already encoded')
        shutil.copy(self.localpath, filename)
        return LocalFile(filename)

    def open(self, mode='r', encoding=None):
        """Return file-like object (actually opens the file for this class)"""
        access_type = self._get_access_type(mode)
        return open(self.localpath, 'r'+access_type, encoding=encoding)

    def read(self, mode='r', encoding=None):
        return self.open(mode=mode, encoding=encoding).read()

    def __iter__(self):
        return iter(self.open())

    def readlines(self):
        return self.open().readlines()

    def __str__(self):
        return 'Local file reference %s' % self.source


class CachedFile(LocalFile):
    """
    Store a copy of the file in a caching directory; delete it if this goes out of scope.
    If pickled, the file gets slurped into memory.
    """
    def __init__(self, filecontainer):
        self.source = filecontainer.source
        self.sourcetype = filecontainer.sourcetype
        self.localpath = self._open_tmpfile()
        filecontainer.put(self.localpath)

    def _open_tmpfile(self):
        """
        Open a temporary, unique file in CACHEDIR (/tmp/cyborgcache) by default.
        Leave it open, assign file handle to self.tmpfile
        """
        tmpfile = get_tempfile()
        path = tmpfile.name
        self.tmpfile = tmpfile
        return path

    def __del__(self):
        os.unlink(self.localpath)

    def __str__(self):
        return 'Cached file from %s @ %s' % (self.source, self.localpath)

