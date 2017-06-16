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
import os
import tempfile
from future.utils import PY2

CACHEDIR = os.path.join(tempfile.gettempdir(), 'pyccc_file_cache')

ENCODING = sys.getdefaultencoding()
if ENCODING == 'ascii':
    ENCODING = 'utf-8'


def get_tempfile():
    if not os.path.exists(CACHEDIR):
        if PY2:
            try:
                os.mkdir(CACHEDIR)
            except OSError:
                if not os.path.isdir(CACHEDIR):
                    raise
        else:
            os.makedirs(CACHEDIR, exist_ok=True)
    tmpfile = tempfile.NamedTemporaryFile(dir=CACHEDIR, delete=False)
    return tmpfile


class FileReferenceBase(object):
    """ The base class for tracking files.

    FileReferenceBase subclass instances are designed to provide abstract access to files regardless
    of how they're stored, including in-memory, on-disk, via URL, or even via API call.

    These objects generally provide read-only functionality.
    We provide some convenience functions that mimic file-like methods (read and __iter__), and
    the ability to get a true filelike object.

    Subclasses must implement:
     * open(mode='r', encoding=None) - return a file-like object (a buffer or actual `file`
                                       instance)

    The following methods and attributes should be implemented when applicable:
     * source (str) - where did this file come from (e.g. file path or URL)
     * sourcetype (str) - text description of the source
     * localpath (str) - path to a copy of this file locally
     * __str__() - should give user an idea of where the file actually lives
     * pickling support (e.g., __reduce__()) - make sure that the file's content will be
                                                 available after the Container object is unpickled

    These methods are implemented, but subclasses may wish to offer more efficient implementations:
     * __iter__(): equivalent of iter(self.open())
     * read(mode, encoding): equivalent of self.open(mode, encoding).read()
     * put(filename): create a local copy of this file and return a reference to it
    """

    def put(self, filename):
        """Write the file to the given path

        Args:
            filename(str): path to write this file to

        Returns:
            LocalFile: reference to the copy of the file stored at ``filename``
        """
        from . import LocalFile

        with self.open('rb') as infile, open(filename, 'wb') as outfile:
            for line in infile:
                outfile.write(infile.read())
        return LocalFile(filename)

    def __iter__(self):
        # This is the worst file-reader ever
        return iter(self.open())

    def read(self, mode='r', encoding=None):
        """ Read the contents of this file. Equivalent to self.open().read()

        Args:
            mode (str): access mode (only reading modes are supported)
            encoding (str): decoding

        Returns:
            str OR bytes: file contents (:class:`bytes` if ``mode`` is binary,
               :class:`str` otherwise)
        """
        return self.open(mode=mode, encoding=encoding).read()

    def cache(self):
        """ Create a locally cached copy of this file and return a reference to it

        Returns:
            CachedFile: reference to locally cached copy of this file
        """
        from . import CachedFile
        return CachedFile(self)

    def _get_access_type(self, mode):
        """ Make sure mode is appropriate; return 'b' for binary access and 't' for text
        """
        access_type = None
        for char in mode:  # figure out whether it's binary or text access
            if char in 'bt':
                if access_type is not None:
                    raise IOError('File mode "%s" contains contradictory flags' % mode)
                access_type = char
            elif char not in 'rbt':
                raise NotImplementedError(
                        '%s objects are read-only; unsupported mode "%s"'%
                        (type(self), mode))

        if access_type is None: access_type = 't'
        return access_type
