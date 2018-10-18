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

import io
import warnings
import os

from . import FileReferenceBase, get_target_path


class BytesContainer(FileReferenceBase):
    """ Holds a file as bytes in memory.

    Note:
        This class holds a file in memory and is therefore not recommended for large files.

        ``BytesContainer`` is the reference implementation for a :class:`FileReferenceBase`
        subclasses

    Args:
        contents (bytes): contents of the file
        encoded_with (str): encoding of the file (default: system default)
    """
    def __init__(self, contents, encoded_with=None, name=None):
        self._contents = contents
        self.encoded_with = encoded_with
        self.source = name
        self.localpath = None
        self.sourcetype = 'runtime'

    def size_bytes(self):
        return len(self._contents)

    def put(self, filename, encoding=None):
        """Write the file to the given path

        Args:
            filename(str): path to write this file to

        Returns:
            LocalFile: reference to the copy of the file stored at ``filename``
        """
        from . import LocalFile

        if os.path.isdir(filename) and self.source is None:
            raise ValueError("Cannot write this object to "
                             "directory %s without an explicit filename." % filename)

        target = get_target_path(filename, self.source)

        if (encoding is not None) and (encoding != self.encoded_with):
            raise ValueError('%s is already encoded as "%s"' % self, self.encoded_with)

        with self.open('rb') as infile, open(target, 'wb') as outfile:
            for line in infile:
                outfile.write(line)
        return LocalFile(target)

    def open(self, mode='r', encoding=None):
        """Return file-like object

        Args:
            mode (str): access mode (only reading modes are supported)
            encoding (str): text decoding method for text access (default: system default)

        Returns:
            io.BytesIO OR io.TextIOWrapper: buffer accessing the file as bytes or characters
        """
        access_type = self._get_access_type(mode)

        if access_type == 't' and encoding is not None and encoding != self.encoded_with:
            warnings.warn('Attempting to decode %s as "%s", but encoding is declared as "%s"'
                          % (self, encoding, self.encoded_with))

        if encoding is None:
            encoding = self.encoded_with

        buffer = io.BytesIO(self._contents)
        if access_type == 'b':
            return buffer
        else:
            return io.TextIOWrapper(buffer, encoding=encoding)

    def __str__(self):
        return 'In-memory file from %s (%d chars)' % (self.source, len(self._contents))

    def __repr__(self):
        return '<%s @ %s>' % (self.__str__(), id(self))


class BZ2String(BytesContainer):
    """ BZ2-compressed file
    """
    def __init__(self, contents, *args, **kwargs):
        self._size = len(contents)
        super(BZ2String, self).__init__(contents, *args, **kwargs)

    def size_bytes(self):
        return self._size

    @property
    def _contents(self):
        import bz2
        return bz2.decompress(self._contents)

    @_contents.setter
    def _contents(self, value):
        import bz2
        self._contents = bz2.compress(value, 1)

    def __str__(self):
        return 'In-memory BZ2-compressed file from %s' % self.source

