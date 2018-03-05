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
from __future__ import print_function, absolute_import, division

import os
from future import standard_library
standard_library.install_aliases()
from future.builtins import *

import sys
import io
from . import FileReferenceBase, ENCODING, get_target_path

PYVERSION = sys.version_info.major


class StringContainer(FileReferenceBase):
    """ In-memory file stored as a text string

    Args:
        contents (str OR bytes): contents of the file
        name (str): descriptive name for the container (highly optional)
        encoding (str): default encoding (for both encoding strings and decoding bytes). If
           not specified, default system encoding is used (usually utf-8)

    Note:
        This handles both unicode (known as `unicode` in py2 and `str` in py3) and raw bytestrings
        (`str` in py2 and `bytes` in py3).
    """
    def __init__(self, contents, name=None, encoding=ENCODING):
        self.source = name
        self.sourcetype = 'runtime'
        self.localpath = None
        self._contents = contents
        self.encoding = encoding

    def open(self, mode='r', encoding=None):
        """Return file-like object

        Args:
            mode (str): access mode (only reading modes are supported)
            encoding (str): encoding type (only for binary access)

        Returns:
            io.BytesIO OR io.TextIOWrapper: buffer accessing the file as bytes or characters
        """
        access_type = self._get_access_type(mode)

        if encoding is None:
            encoding = self.encoding

        # here, we face the task of returning the correct data type
        if access_type == 'b':
            if not self._isbytes:
                content = self._contents.encode(encoding)  # unicode in, bytes out
            else:
                content = self._contents  # bytes in, bytes out
            return io.BytesIO(content)
        else:
            assert access_type == 't'
            if PYVERSION == 2 and self._isbytes:
                return io.BytesIO(self._contents)  # bytes in, bytes out (python 2 only)
            elif self._isbytes:
                content = self._contents.decode(encoding)  # bytes in, unicode out
            else:
                content = self._contents  # unicode in, unicode out
            return io.StringIO(content)

    @property
    def _isbytes(self):
        if PYVERSION == 2:
            return not isinstance(self._contents, unicode)
        else:
            assert PYVERSION >= 3
            return isinstance(self._contents, bytes)

    def put(self, filename, encoding=None):
        """Write the file to the given path

        Args:
            filename (str): path to write this file to
            encoding (str): file encoding (default: system default)

        Returns:
            LocalFile: reference to the copy of the file stored at ``filename``
        """
        from . import LocalFile

        if os.path.isdir(filename) and self.source is None:
            raise ValueError("Cannot write this object to "
                             "directory %s without an explicit filename." % filename)

        target = get_target_path(filename, self.source)

        if encoding is None:
            encoding = self.encoding

        if self._isbytes:
            kwargs = {'mode': 'wb'}
        else:
            kwargs = {'mode': 'w', 'encoding': encoding}

        with open(target, **kwargs) as outfile:
            outfile.write(self._contents)

        return LocalFile(target, encoded_with=encoding)

