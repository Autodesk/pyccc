import pytest
import pyccc

"""Super-basic tests just to make sure pyccc installed correctly"""

registered_types = {}


def typedfixture(*types, **kwargs):
    """This is a decorator that lets us associate fixtures with one or more arbitrary types.
    We'll later use this type to determine what tests to run on the result"""

    def fixture_wrapper(func):
        for t in types:
            registered_types.setdefault(t, []).append(func.__name__)
        return pytest.fixture(**kwargs)(func)

    return fixture_wrapper


@typedfixture('engine')
def subprocess_engine():
    return pyccc.Subprocess()


@pytest.mark.parametrize('objkey', registered_types['engine'])
def test_hello_world(objkey, request):
    engine = request.getfuncargvalue(objkey)
    job = engine.launch('alpine', 'echo hello world')
    job.wait()
    assert job.stdout.strip() == 'hello world'


@pytest.mark.parametrize('objkey', registered_types['engine'])
def test_sleep_raises_JobStillRunning(objkey, request):
    engine = request.getfuncargvalue(objkey)
    job = engine.launch('alpine', 'sleep 5; echo done')
    with pytest.raises(pyccc.JobStillRunning):
        job.stdout
    job.wait()
    assert job.stdout.strip() == 'done'



