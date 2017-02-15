import pytest
import pyccc

from .engine_fixtures import *

"""Super-basic tests just to make sure pyccc installed correctly"""


@pytest.mark.parametrize('objkey', registered_types['engine'])
def test_hello_world(objkey, request):
    engine = request.getfuncargvalue(objkey)
    job = engine.launch('alpine', 'echo hello world')
    job.wait()
    assert job.stdout.strip() == 'hello world'


def _testfun(x):
    return x+1


@pytest.mark.parametrize('objkey', registered_types['engine'])
def test_input_ouput_files(objkey, request):
    engine = request.getfuncargvalue(objkey)
    job = engine.launch(image='alpine',
                        command='cat a.txt b.txt > out.txt',
                        inputs={'a.txt': 'a',
                                'b.txt': pyccc.StringContainer('b')})
    job.wait()
    assert job.get_output('out.txt').read().strip() == 'ab'


@pytest.mark.parametrize('objkey', registered_types['engine'])
def test_python_run(objkey, request):
    engine = request.getfuncargvalue(objkey)
    pycall = pyccc.PythonCall(_testfun, 5)
    job = engine.launch('python:2.7-slim', pycall)
    job.wait()
    assert job.result == 6


@pytest.mark.parametrize('objkey', registered_types['engine'])
def test_sleep_raises_JobStillRunning(objkey, request):
    engine = request.getfuncargvalue(objkey)
    job = engine.launch('alpine', 'sleep 5; echo done')
    with pytest.raises(pyccc.JobStillRunning):
        job.stdout
    job.wait()
    assert job.stdout.strip() == 'done'

