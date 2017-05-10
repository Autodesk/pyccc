from itertools import product

import sys
import pytest
import pyccc

"""Basic test battery for regular and python jobs on all underlying engines"""

REMOTE_PYTHON_VERSIONS = {2: '2.7', 3: '3.6'}
PYVERSION = REMOTE_PYTHON_VERSIONS[sys.version_info.major]

fixture_types = {}



def typedfixture(*types, **kwargs):
    """This is a decorator that lets us associate fixtures with one or more arbitrary types.
    This makes it easy, later, to run the same test on all fixtures of a given type"""

    def fixture_wrapper(func):
        for t in types:
            fixture_types.setdefault(t, []).append(func.__name__)
        return pytest.fixture(**kwargs)(func)

    return fixture_wrapper


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
# Fixtures        #
###################

@typedfixture('engine')
def subprocess_engine():
    return pyccc.Subprocess()


@typedfixture('engine')
def public_ccc_engine():
    if not pytest.config.getoption("--testccc"):
        pytest.skip("need --testccc option to run")
    else:
        return pyccc.CloudComputeCannon('cloudcomputecannon.bionano.autodesk.com:9000')


@typedfixture('engine')
def local_docker_engine():
    return pyccc.Docker()


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
    job = engine.launch('python:%s-slim'%PYVERSION, pycall, interpreter=PYVERSION)
    job.wait()
    assert job.result == 6


@pytest.mark.parametrize('fixture', fixture_types['engine'])
def test_python_instance_method(fixture, request):
    engine = request.getfuncargvalue(fixture)
    obj = _TestCls()
    pycall = pyccc.PythonCall(obj.increment, by=2)
    job = engine.launch('python:%s-slim'%PYVERSION, pycall, interpreter=PYVERSION)
    job.wait()

    assert job.result == 2
    assert job.updated_object.x == 2


@pytest.mark.parametrize('fixture', fixture_types['engine'])
def test_python_reraises_exception(fixture, request):
    engine = request.getfuncargvalue(fixture)
    pycall = pyccc.PythonCall(_raise_valueerror, 'this is my message')
    job = engine.launch('python:%s-slim'%PYVERSION, pycall, interpreter=PYVERSION)
    job.wait()

    with pytest.raises(ValueError):
        job.result

