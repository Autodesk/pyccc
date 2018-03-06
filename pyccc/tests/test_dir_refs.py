import os

import itertools
from .engine_fixtures import *

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
    return _get_dir_from_job_on_engine(engine, dir_archive)


@pytest.fixture
def subprocess_dir_reference(dir_archive):
    engine = pyccc.Subprocess()
    return _get_dir_from_job_on_engine(engine, dir_archive)


def _get_dir_from_job_on_engine(engine, dir_archive):
    archive_file = pyccc.LocalFile(dir_archive.archive_path)

    job = engine.launch(image='alpine',
                        workingdir='/test',
                        inputs={'/test/archive.tar': archive_file},
                        command='tar xvf /test/archive.tar')
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


def test_get_directory_with_subdirs(tmpdir):
    engine = pyccc.Docker()
    tmpdir = str(tmpdir)

    cmd = ("mkdir -p /opt/blah/fugu && echo a > /opt/blah/a"
           " && echo b > /opt/blah/b && echo fish > /opt/blah/fugu/fish")

    job = engine.launch(image='alpine',
                        workingdir='/test',
                        command=cmd)
    job.wait()
    outdir = job.get_directory('/opt/blah')
    outdir.put(tmpdir)
    for path in ['a', 'b', 'fugu/fish']:
        assert os.path.exists(os.path.join(tmpdir, 'blah', path))


def test_tar_archive_not_expanded(dir_archive):
    engine = pyccc.Docker()
    archive_file = pyccc.LocalFile(dir_archive.archive_path)
    job = engine.launch(image='alpine',
                        workingdir='/test',
                        inputs={'/root/archive.tar': archive_file},
                        command='ls /root')
    job.wait()
    files = job.stdout.split()
    assert 'archive.tar' in files
    assert 'data' not in files

