# -*- coding: UTF-8 -*-
import pytest
import uuid

import pyccc

fixture_types = {}


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


def _gen_tempfile_path():
    return '/tmp/pyccc_test_%s.txt' % uuid.uuid4()


@typedfixture('container')
def bytescontainer():
    return pyccc.files.BytesContainer(BYTES_CONTENT)


@typedfixture('container')
def stringcontainer():
    return pyccc.files.StringContainer(STRING_CONTENT)


@typedfixture('container')
def localfile_from_bytes(bytescontainer):
    return bytescontainer.put(_gen_tempfile_path())


@typedfixture('container')
def localfile_from_string(stringcontainer):
    return stringcontainer.put(_gen_tempfile_path())


@typedfixture('container')
def localfile_in_memory(bytescontainer):
    localfile = bytescontainer.put(_gen_tempfile_path())
    return pyccc.FileContainer(localfile.localpath)


@pytest.mark.parametrize('fixture', fixture_types['container'])
def test_file_container(fixture, request):
    my_container = request.getfuncargvalue(fixture)
    assert list(my_container) == LINES_CONTENT
    assert my_container.read() == STRING_CONTENT
    assert my_container.read('rb') == BYTES_CONTENT


@pytest.mark.parametrize('fixture', fixture_types['container'])
def test_containers_open_filelike_object(fixture, request):
    ctr = request.getfuncargvalue(fixture)
    assert list(ctr.open('r')) == LINES_CONTENT
    assert ctr.open('r').read() == STRING_CONTENT
    assert ctr.open('rb').read() == BYTES_CONTENT

