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
import os
import shutil
import tempfile
import io
import urllib2
import tarfile
import StringIO
import socket

try:
    from pyccc.config import config as cfg

    cachedir = cfg.CACHEDIR
except ImportError:
    cachedir = '/tmp/cyborgcache/'


def get_tempfile():
    if not os.path.exists(cachedir):
        os.mkdir(cachedir)
    tmpfile = tempfile.NamedTemporaryFile(dir=cachedir, delete=False)
    return tmpfile


class FileContainer(object):
    """
    Reads a file from the filesystem into memory.

    This class is both the reference implementation and our other file-tracking classes.
    These objects generally provide read-only functionality.
    We provide some convenience functions that mimic file-like methods (read and __iter__), and
    the ability to get a true filelike object.

    These classes should, at a minimum, implement the following read-only file-like methods:
     * read() - return the file's _contents
     * __iter__() - an iterator over the lines in the file
     * readlines - returns list(self.__iter__())
     * open(mode='r') - return a true file-like object (a buffer or actual `file` instance)

    Derived classes should provide these methods and attributes:
     * put(filename) - write this file to disk, return reference to new file
     * cache() - temporarily cache this file and return a reference to the cached version
     * source (str) - where did this file come from?
     * sourcetype (str) - text description of the source
     * localpath (str) - where this lives on the local filesystem (or None for in-memory objects)
     * __str__() - should give user an idea of where the file actually lives
     * pickling support (e.g., __reduce__()) - make sure that the file's content will be
                                                 available after the Container object is unpickled
    """

    def __init__(self, filename):
        self.source = filename
        self.sourcetype = 'Local file on %s' % socket.gethostname()
        self.localpath = None
        with open(filename, 'r') as infile:
            self._contents = infile.read()

    def put(self, filename):
        """Write the file to the given localpath"""
        with open(filename, 'w') as outfile:
            outfile.write(self._contents)
        return LocalFile(filename)

    def __iter__(self):
        """This is the worst file-reader ever"""
        ipos = 0
        buff = []
        contents = self._contents
        while ipos < len(contents):
            c = contents[ipos]
            buff.append(c)
            if c == '\n':
                yield ''.join(buff)
                buff = []
            ipos += 1
        if buff: yield buff

    def readlines(self):
        return self._contents.split('\n')

    def read(self):
        return self._contents

    def cache(self):
        return CachedFile(self)

    def open(self, mode='r'):
        """Return file-like object"""
        if mode != 'r':
            raise NotImplementedError('FileContainer only supports "r" access mode')
        return io.BytesIO(self._contents)

    def __str__(self):
        return 'In-memory file from %s: %s (%d chars)' % (self.sourcetype, self.source, len(self._contents))

    def __repr__(self):
        return '<%s>' % self.__str__()


class StringContainer(FileContainer):
    def __init__(self, contents, name='string'):
        self.source = name
        self.sourcetype = 'python'
        self.localpath = None
        self._contents = contents

    def __str__(self):
        return 'In-memory file from %s (%d chars)' % (self.source, len(self._contents))

    def __repr__(self):
        return '<%s @ %s>' % (self.__str__(), id(self))


class BZ2String(StringContainer):
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


class LocalFile(FileContainer):
    """
    A reference to a local file.
    WARNING: there will be issues if the file is moved or modified!
    Some subclasses take care of this
    """

    def __reduce__(self):
        return StringContainer, (self.read(),)

    def __init__(self, path, check_exists=True):
        if check_exists and not os.path.exists(path):
            raise IOError('File not found: %s' % path)

        self.source = path
        self.localpath = self.source
        self.sourcetype = 'Local file on %s' % socket.gethostname()

    def put(self, filename):
        shutil.copy(self.localpath, filename)
        return LocalFile(filename)

    def open(self, mode='r'):
        """Return file-like object (actually opens the file for this class)"""
        if mode != 'r':
            raise NotImplementedError('FileContainer only supports "r" access mode')
        return open(self.localpath, mode)

    def read(self):
        return self.open().read()

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
        Open a temporary, unique file in cachedir (/tmp/cyborgcache) by default.
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


class _FetchFunction(object):
    """Convenience descriptor for methods that need to download a file before doing anything"""
    def __init__(self, funcname):
        self.funcname = funcname

    def __get__(self, instance, cls):
        instance.download()
        return getattr(super(LazyFetcherBase, instance), self.funcname)


class LazyFetcherBase(CachedFile):
    """
    A base class for for dealing with files that need to be downloaded - they are cached locally when downloaded.
    """
    def __init__(self):
        self._fetched = False
        self.localpath = None

    put = _FetchFunction('put')
    open = _FetchFunction('open')
    read = _FetchFunction('read')
    readlines = _FetchFunction('readlines')
    __iter__ = _FetchFunction('__iter__')

    def download(self):
        if not self._fetched:
            self._fetch()
            self._fetched = True

    def _fetch(self):
        raise NotImplemented("_fetch needs to be implemented by subclass")

    def __del__(self):
        if self._fetched:
            super(LazyFetcherBase, self).__del__()

    def __str__(self):
        if self._fetched:
            return super(LazyFetcherBase, self).__str__()
        else:
            return 'Reference to %s (not downloaded)' % self.source


class HttpContainer(LazyFetcherBase):
    """
    Lazily fetched file on the web. Will cache it in cachedir ('/tmp/cyborgcache')
    by default, then treat it as a CachedFile class

    Unlike other remote files, this one doesn't preserve the file contents when pickled;
    instead, we assume that it should still be accessible (not always a good assumption!)
    """
    def __reduce__(self):
        return self.__class__, (self.source,)

    def __init__(self, url):
        self.source = url
        self.sourcetype = 'HTTP request'
        super(HttpContainer, self).__init__()

    def _fetch(self):
        self._open_tmpfile()
        request = urllib2.urlopen(self.source)
        for line in request:
            self.tmpfile.write(line)
        request.close()
        self.tmpfile.close()
        self.localpath = self.tmpfile.name
        self._fetched = True


class LazyDockerCopy(LazyFetcherBase):
    """
    Lazily copies the file from the worker.
    This is, of course, problematic if the worker is not accessible from the client.
    Persistence is also a problem
    """
    def __init__(self, dockerhost, containerid, containerpath):
        self.source = "%s (%s)://%s" % (dockerhost, containerid, containerpath)
        self.sourcetype = 'Docker container'
        self.dockerhost = dockerhost
        self.containerpath = containerpath
        self.containerid = containerid
        self.basename = os.path.basename(containerpath)
        super(LazyDockerCopy, self).__init__()

    def _fetch(self):
        """
        Note that docker.copy returns an uncompressed tar stream, which
        was undocumented as of this writing.
        See http://stackoverflow.com/questions/22683410/docker-python-client-api-copy
        """
        import docker
        self._open_tmpfile()
        client = docker.Client(**self.dockerhost)
        request = client.copy(self.containerid, self.containerpath)

        # from stackoverflow link
        filelike = StringIO.StringIO(request.read())
        tar = tarfile.open(fileobj=filelike)
        file = tar.extractfile(os.path.basename(self.containerpath))
        # end SOFlow
        self.tmpfile.write(file.read())
        request.close()
        self.tmpfile.close()
        self.localpath = self.tmpfile.name
        self._fetched = True
