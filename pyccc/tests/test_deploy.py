import pytest
import pyccc

"""Super-basic tests just to make sure pyccc installed correctly"""

registered_types = {}


def typedfixture(*types, **kwargs):
    """This is a decorator that lets us associate fixtures with one or more arbitrary types.
    This makes it easy, later, to run the same test on all fixtures of a given type"""

    def fixture_wrapper(func):
        for t in types:
            registered_types.setdefault(t, []).append(func.__name__)
        return pytest.fixture(**kwargs)(func)

    return fixture_wrapper


@typedfixture('engine')
def subprocess_engine():
    return pyccc.Subprocess()


@typedfixture('engine')
def public_ccc_engine():
    return pyccc.CloudComputeCannon('cloudcomputecannon.bionano.autodesk.com:9000')


@typedfixture('engine')
def local_docker_engine():
    return pyccc.Docker('unix://var/run/docker.sock')


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



