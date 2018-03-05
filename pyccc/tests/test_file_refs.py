# -*- coding: UTF-8 -*-
import os
import sys
import pickle

import itertools
import pytest

import pyccc

fixture_types = {}

PYVERSION = sys.version_info.major
THISDIR = os.path.dirname(__file__)


if PYVERSION >= 3:
    unicode = str  # we'll use "unicode" and "bytes" just to be completely clear

def typedfixture(*types, **kwargs):
    """This is a decorator that lets us associate fixtures with one or more arbitrary types.
    This makes it easy, later, to run the same test on all fixtures of a given type"""

    def fixture_wrapper(func):
        for t in types:
            fixture_types.setdefault(t, []).append(func.__name__)
        return pytest.fixture(**kwargs)(func)

    return fixture_wrapper

BYTES_CONTENT = b'abcd\n1234'
STRING_CONTENT = u'abcd\n1234'
LINES_CONTENT = ['abcd\n',
                 '1234']


@typedfixture('file_ref')
def bytescontainer():
    return pyccc.files.BytesContainer(BYTES_CONTENT)


@typedfixture('file_ref')
def stringcontainer():
    return pyccc.files.StringContainer(STRING_CONTENT)

def _make_subtempdir(tmpdir):
    """ Makes a temp dir UNDERNEATH the current tempdir
    """
    subtempdir = os.path.join(str(tmpdir), 'fixture_tmp')
    os.mkdir(subtempdir)
    return subtempdir

@typedfixture('file_ref')
def localfile_from_bytes(bytescontainer, tmpdir):
    subtempdir = _make_subtempdir(tmpdir)
    return bytescontainer.put(os.path.join(subtempdir, 'bytesfile'))


@typedfixture('file_ref')
def localfile_from_string(stringcontainer, tmpdir):
    subtempdir = _make_subtempdir(tmpdir)
    return stringcontainer.put(os.path.join(subtempdir, 'strfile'))


@typedfixture('file_ref')
def localfile_in_memory(bytescontainer, tmpdir):
    subtempdir = _make_subtempdir(tmpdir)
    localfile = bytescontainer.put(os.path.join(subtempdir, 'bytefile'))
    return pyccc.FileContainer(localfile.localpath)


@typedfixture('file_ref')
def http_reference(httpserver):
    httpserver.serve_content(BYTES_CONTENT)
    ref = pyccc.HttpContainer(httpserver.url)
    return ref


@typedfixture('file_ref')
def docker_output_reference():
    import pyccc
    engine = pyccc.engines.Docker()
    job = engine.launch(image='alpine',
                        inputs={"/in.txt": BYTES_CONTENT},
                        command="cp /in.txt /out.txt")
    job.wait()
    return job.get_output('/out.txt')


@pytest.mark.parametrize('fixture', fixture_types['file_ref'])
def test_file_container(fixture, request):
    my_container = request.getfuncargvalue(fixture)
    assert list(my_container) == LINES_CONTENT
    assert my_container.read() == STRING_CONTENT
    assert my_container.read('rb') == BYTES_CONTENT


@pytest.mark.parametrize('fixture', fixture_types['file_ref'])
def test_containers_open_filelike_object(fixture, request):
    ctr = request.getfuncargvalue(fixture)
    assert list(ctr.open('r')) == LINES_CONTENT
    assert ctr.open('r').read() == STRING_CONTENT
    assert ctr.open('rb').read() == BYTES_CONTENT


def test_stringcontainer_handles_unicode():
    angstrom = u'Å'
    s1 = pyccc.files.StringContainer(angstrom)

    readval = s1.read()
    assert readval == angstrom
    assert isinstance(readval, unicode)

    readbin = s1.read(mode='rb')
    assert isinstance(readbin, bytes)
    assert readbin.decode(pyccc.files.ENCODING) == readval
    assert readval.encode(pyccc.files.ENCODING) == readbin


@pytest.mark.parametrize('encoding', 'latin-1 utf-8 utf-7 utf-32 utf_16_be mac_roman'.split())
def test_stringcontainer_handles_bytes(encoding):
    angstrom = u'Å'
    angstrom_bytes = angstrom.encode(encoding)
    assert isinstance(angstrom_bytes, bytes)  # just to be clear

    s1 = pyccc.files.StringContainer(angstrom_bytes, encoding=encoding)

    readval = s1.read()
    if PYVERSION == 2:
        assert isinstance(readval, bytes)
        assert readval == angstrom_bytes
        assert readval.decode(encoding) == angstrom
    else:
        assert PYVERSION >= 3
        assert readval == angstrom
        assert isinstance(readval, unicode)

    readbin = s1.read(mode='rb')
    assert isinstance(readbin, bytes)
    assert readbin.decode(encoding) == angstrom


@pytest.mark.parametrize('fixture', fixture_types['file_ref'])
def test_containers_are_pickleable(fixture, request):
    ctr = request.getfuncargvalue(fixture)
    newctr = pickle.loads(pickle.dumps(ctr))
    assert newctr.read() == ctr.read()


@pytest.mark.parametrize(['fixture', 'putdir'],
                         itertools.product(fixture_types['file_ref'],
                                           ['', 'my_file.txt']))
def test_put_file_to_location(request, fixture, tmpdir, putdir):
    tmpdir = str(tmpdir)
    fileref = request.getfixturevalue(fixture)

    if fileref.__class__ in (pyccc.BytesContainer, pyccc.StringContainer) and not putdir:
        with pytest.raises(ValueError):
            fileref.put(tmpdir)
        return  # these classes need explicit filenames for put

    if putdir:
        target = os.path.join(tmpdir, putdir)
        destination = target
    else:
        target = os.path.join(tmpdir, os.path.basename(fileref.source))
        destination = tmpdir

    assert not os.path.exists(target)
    fileref.put(destination)
    assert os.path.exists(target)

    with open(target, 'r') as ff:
        assert ff.read() == STRING_CONTENT
    with open(target, 'rb') as ff:
        assert ff.read() == BYTES_CONTENT
