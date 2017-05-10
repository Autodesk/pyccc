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

import sys
import io

from . import FileReferenceBase, BytesContainer


class StringContainer(FileReferenceBase):
    """ In-memory file stored as a text string

    Args:
        contents (str): contents of the file
        name (str): descriptive name for the container (highly optional)

    Note:
        For backwards compatibility, if ``contents`` is a byte string (``str`` in python 2,
        ``bytes`` in python 3), this will produce a BytesContainer object
    """

    def __new__(cls, contents, **kwargs):
        """ If a user calls this with a :class:`bytes` object, instantiate a BytesContainer
        instead of a StringContainer. This is for the convenience of python 2 API users.
        """
        if isinstance(contents, str):
            return super().__new__(cls)
        else:
            return BytesContainer(contents, **kwargs)

    def __init__(self, contents, name='string'):
        self.source = name
        self.sourcetype = 'python'
        self.localpath = None
        self._contents = contents

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
            encoding = sys.getdefaultencoding()

        if access_type == 'b':
            return io.BytesIO(self._contents.encode(encoding))
        else:
            return io.StringIO(self._contents)

    def put(self, filename, encoding=None):
        """Write the file to the given path

        Args:
            filename (str): path to write this file to
            encoding (str): file encoding (default: system default)

        Returns:
            LocalFile: reference to the copy of the file stored at ``filename``
        """
        from . import LocalFile

        with self.open() as infile, open(filename, 'w', encoding=encoding) as outfile:
            for line in infile:
                outfile.write(line)

        return LocalFile(filename, encoded_with=encoding)

