import pytest
import pyccc

__all__ = 'typedfixture fixture_types subprocess_engine public_ccc_engine local_docker_engine'.split()

fixture_types = {}


def typedfixture(*types, **kwargs):
    """This is a decorator that lets us associate fixtures with one or more arbitrary types.
    This makes it easy, later, to run the same test on all fixtures of a given type"""

    def fixture_wrapper(func):
        for t in types:
            fixture_types.setdefault(t, []).append(func.__name__)
        return pytest.fixture(**kwargs)(func)

    return fixture_wrapper


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
