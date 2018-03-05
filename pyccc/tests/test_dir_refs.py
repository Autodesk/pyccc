import os

import itertools
import pytest
import pyccc

THISDIR = os.path.dirname(__file__)


@pytest.fixture
def localdir():
    return pyccc.files.LocalDirectoryReference(os.path.join(THISDIR, 'data'))


@pytest.fixture
def dir_archive(tmpdir):
    return _make_dir_archive(tmpdir, False)


@pytest.fixture
def compressed_dir_archive(tmpdir):
    return _make_dir_archive(tmpdir, True)


def _make_dir_archive(tmpdir, compress):
    import subprocess
    tmpdir = str(tmpdir)
    if compress:
        fname = os.path.join(tmpdir, 'archive.tar.gz')
        opts = 'z'
    else:
        fname = os.path.join(tmpdir, 'archive.tar')
        opts = ''

    subprocess.check_call(['tar', 'c%sf' % opts, fname, 'data'],
                          cwd=THISDIR)
    return pyccc.files.DirectoryArchive(fname, 'data')


@pytest.fixture
def docker_dir_archive(dir_archive):
    engine = pyccc.Docker()

    job = engine.launch(image='alpine',
                        workingdir='/test',
                        inputs={'/test': dir_archive},
                        command='tar xvzf /test/archive.tar')
    job.wait()
    return job.get_directory('/test/data')


@pytest.mark.parametrize(['fixturename', 'reldir'],
                         itertools.product(['localdir', 'dir_archive',
                                            'compressed_dir_archive', 'docker_dir_archive'],
                                           ['', 'mydir']))
def test_put_directory_reference_with_renaming(request, fixturename, tmpdir, reldir):
    import filecmp
    tmpdir = str(tmpdir)
    destination = os.path.join(tmpdir, reldir)
    fileref = request.getfixturevalue(fixturename)
    fileref.put(destination)

    source = os.path.join(THISDIR, 'data')
    if reldir:
        target = os.path.join(tmpdir, reldir)
    else:
        target = os.path.join(tmpdir, 'data')
    match, mismatch, errors = filecmp.cmpfiles(source,
                                               target, ['a', 'b'])
    assert not mismatch
    assert not errors
