import os
import pytest
from .engine_fixtures import subprocess_engine, local_docker_engine

"""
Tests of features and quirks specific to engines
"""

@pytest.fixture
def set_env_var():
    import os
    assert 'NULL123' not in os.environ, "Bleeding environment"
    os.environ['NULL123'] = 'nullabc'
    yield
    del os.environ['NULL123']


def test_subprocess_environment_preserved(subprocess_engine, set_env_var):
    job = subprocess_engine.launch(command='echo $NULL123', image='python:2.7-slim')
    job.wait()
    assert job.stdout.strip() == 'nullabc'


def test_readonly_docker_volume_mount(local_docker_engine):
    engine = local_docker_engine
    mountdir = '/tmp'
    job = engine.launch(image='docker',
                        command='echo blah > /mounted/blah',
                        engine_options={'volumes':
                                            {mountdir: ('/mounted', 'ro')}})
    job.wait()
    assert isinstance(job.exitcode, int)
    assert job.exitcode != 0


def test_set_workingdir_docker(local_docker_engine):
    engine = local_docker_engine
    job = engine.launch(image='docker', command='pwd', workingdir='/testtest-dir-test')
    job.wait()
    assert job.stdout.strip() == '/testtest-dir-test'


def test_docker_volume_mount(local_docker_engine):
    """
    Note:
        The test context is not necessarily the same as the bind mount context!
        These tests will run in containers themselves, so we can't assume
        that any directories accessible to the tests are bind-mountable.

        Therefore we just test a named volume here.
    """
    import subprocess, uuid
    engine = local_docker_engine
    key = uuid.uuid4()
    volname = 'my-mounted-volume-%s' % key

    # Create a named volume with a file named "keyfile" containing a random uuid4
    subprocess.check_call(('docker volume rm {vn}; docker volume create {vn}; '
                          'docker run -v {vn}:/mounted alpine sh -c "echo {k} > /mounted/keyfile"')
                          .format(vn=volname, k=key),
                          shell=True)

    job = engine.launch(image='docker',
                        command='cat /mounted/keyfile',
                        engine_options={'volumes': {volname: '/mounted'}})
    job.wait()
    result = job.stdout.strip()
    assert result == str(key)


@pytest.mark.skipif('CI_PROJECT_ID' in os.environ,
                    reason="Can't mount docker socket in codeship")
def test_docker_socket_mount_with_engine_option(local_docker_engine):
    engine = local_docker_engine

    job = engine.launch(image='docker',
                        command='docker ps -q --no-trunc',
                        engine_options={'mount_docker_socket': True})
    job.wait()
    running = job.stdout.strip().splitlines()
    assert job.jobid in running


@pytest.mark.skipif('CI_PROJECT_ID' in os.environ,
                    reason="Can't mount docker socket in codeship")
def test_docker_socket_mount_withdocker_option(local_docker_engine):
    engine = local_docker_engine

    job = engine.launch(image='docker',
                        command='docker ps -q --no-trunc',
                        withdocker=True)
    job.wait()
    running = job.stdout.strip().splitlines()
    assert job.jobid in running
