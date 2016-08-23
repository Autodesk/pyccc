import pytest
import pyccc

"""Basic test battery for the underlying engines"""

registered_types = {}


def typedfixture(*types, **kwargs):
    """This is a decorator that lets us associate fixtures with one or more arbitrary types.
    This makes it easy, later, to run the same test on all fixtures of a given type"""

    def fixture_wrapper(func):
        for t in types:
            registered_types.setdefault(t, []).append(func.__name__)
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


# @typedfixture('engine')  # disabled temporarily
def public_ccc_engine():
    return pyccc.CloudComputeCannon('cloudcomputecannon.bionano.autodesk.com:9000')


@typedfixture('engine')
def local_docker_engine():
    return pyccc.Docker('unix://var/run/docker.sock')


###################
# Tests           #
###################
@pytest.mark.parametrize('objkey', registered_types['engine'])
def test_hello_world(objkey, request):
    engine = request.getfuncargvalue(objkey)
    job = engine.launch('alpine', 'echo hello world')
    job.wait()
    assert job.stdout.strip() == 'hello world'


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
def test_python_function(objkey, request):
    engine = request.getfuncargvalue(objkey)
    pycall = pyccc.PythonCall(_testfun, 5)
    job = engine.launch('python:2.7-slim', pycall)
    job.wait()
    assert job.result == 6


@pytest.mark.parametrize('objkey', registered_types['engine'])
def test_python_instance_method(objkey, request):
    engine = request.getfuncargvalue(objkey)
    obj = _TestCls()
    pycall = pyccc.PythonCall(obj.increment, by=2)
    job = engine.launch('python:2.7-slim', pycall)
    job.wait()

    assert job.result == 2
    assert job.updated_object.x == 2


@pytest.mark.parametrize('objkey', registered_types['engine'])
def test_python_reraises_exception(objkey, request):
    engine = request.getfuncargvalue(objkey)
    pycall = pyccc.PythonCall(_raise_valueerror, 'this is my message')
    job = engine.launch('python:2.7-slim', pycall)
    job.wait()

    with pytest.raises(ValueError):
        job.result


@pytest.mark.parametrize('objkey', registered_types['engine'])
def test_sleep_raises_jobstillrunning(objkey, request):
    engine = request.getfuncargvalue(objkey)
    job = engine.launch('alpine', 'sleep 5; echo done')
    with pytest.raises(pyccc.JobStillRunning):
        job.stdout
    job.wait()
    assert job.stdout.strip() == 'done'



