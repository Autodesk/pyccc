import sys
import pytest
import pyccc
from .engine_fixtures import *

"""Basic test battery for regular and python jobs on all underlying engines"""

REMOTE_PYTHON_VERSIONS = {2: '2.7', 3: '3.6'}
PYVERSION = REMOTE_PYTHON_VERSIONS[sys.version_info.major]
PYIMAGE = 'python:%s-slim' % PYVERSION


########################
# Python test objects  #
########################
def _testfun(x):
    return x+1


class _TestCls(object):
    def __init__(self):
        self.x = 0

    def increment(self, by=1):
        self.x += by
        return self.x


def _raise_valueerror(msg):
    raise ValueError(msg)



###################
# Tests           #
###################
@pytest.mark.parametrize('fixture', fixture_types['engine'])
def test_hello_world(fixture, request):
    engine = request.getfuncargvalue(fixture)
    job = engine.launch('alpine', 'echo hello world')
    job.wait()
    assert job.stdout.strip() == 'hello world'


@pytest.mark.parametrize('fixture', fixture_types['engine'])
def test_input_ouput_files(fixture, request):
    engine = request.getfuncargvalue(fixture)
    job = engine.launch(image='alpine',
                        command='cat a.txt b.txt > out.txt',
                        inputs={'a.txt': 'a',
                                'b.txt': pyccc.StringContainer('b')})
    job.wait()
    assert job.get_output('out.txt').read().strip() == 'ab'


@pytest.mark.parametrize('fixture', fixture_types['engine'])
def test_sleep_raises_jobstillrunning(fixture, request):
    engine = request.getfuncargvalue(fixture)
    job = engine.launch('alpine', 'sleep 5; echo done')
    with pytest.raises(pyccc.JobStillRunning):
        job.stdout
    job.wait()
    assert job.stdout.strip() == 'done'


@pytest.mark.parametrize('fixture', fixture_types['engine'])
def test_python_function(fixture, request):
    engine = request.getfuncargvalue(fixture)
    pycall = pyccc.PythonCall(_testfun, 5)
    job = engine.launch(PYIMAGE, pycall, interpreter=PYVERSION)
    job.wait()
    assert job.result == 6


@pytest.mark.parametrize('fixture', fixture_types['engine'])
def test_python_instance_method(fixture, request):
    engine = request.getfuncargvalue(fixture)
    obj = _TestCls()
    pycall = pyccc.PythonCall(obj.increment, by=2)
    job = engine.launch(PYIMAGE, pycall, interpreter=PYVERSION)
    job.wait()

    assert job.result == 2
    assert job.updated_object.x == 2


@pytest.mark.parametrize('fixture', fixture_types['engine'])
def test_python_reraises_exception(fixture, request):
    engine = request.getfuncargvalue(fixture)
    pycall = pyccc.PythonCall(_raise_valueerror, 'this is my message')
    job = engine.launch(PYIMAGE, pycall, interpreter=PYVERSION)
    job.wait()

    with pytest.raises(ValueError):
        job.result


@pytest.mark.parametrize('fixture', fixture_types['engine'])
def test_builtin_imethod(fixture, request):
    engine = request.getfuncargvalue(fixture)
    mylist = [3, 2, 1]
    fn = pyccc.PythonCall(mylist.sort)
    job = engine.launch(image=PYIMAGE, command=fn, interpreter=PYVERSION)
    job.wait()

    assert job.result is None  # since sort doesn't return anything
    assert job.updated_object == [1, 2, 3]


@pytest.mark.parametrize('fixture', fixture_types['engine'])
def test_builtin_function(fixture, request):
    engine = request.getfuncargvalue(fixture)
    mylist = [3, 2, 1]
    fn = pyccc.PythonCall(sorted, mylist)
    job = engine.launch(image=PYIMAGE, command=fn, interpreter=PYVERSION)
    job.wait()

    assert job.result == [1,2,3]



