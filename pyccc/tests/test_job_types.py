# -*- coding: utf-8 -*-
import sys
import pytest
import pyccc
from .engine_fixtures import *
from . import function_tests

"""Basic test battery for regular and python jobs on all underlying engines"""

PYVERSION = '%s.%s' % (sys.version_info.major, sys.version_info.minor)
PYIMAGE = 'python:%s-slim' % PYVERSION


########################
# Python test objects  #
########################

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
def test_job_status(fixture, request):
    engine = request.getfuncargvalue(fixture)
    job = engine.launch('alpine', 'sleep 3', submit=False)
    assert job.status.lower() == 'unsubmitted'
    job.submit()
    assert job.status.lower() in ('queued', 'running', 'downloading')
    job.wait()
    assert job.status.lower() == 'finished'


@pytest.mark.parametrize('fixture', fixture_types['engine'])
def test_file_glob(fixture, request):
    engine = request.getfuncargvalue(fixture)
    job = engine.launch('alpine', 'touch a.txt b c d.txt e.gif')
    job.wait()

    assert set(job.get_output().keys()) <= set('a.txt b c d.txt e.gif'.split())
    assert set(job.glob_output('*.txt').keys()) == set('a.txt d.txt'.split())


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
    pycall = pyccc.PythonCall(function_tests.fn, 5)
    job = engine.launch(PYIMAGE, pycall, interpreter=PYVERSION)
    job.wait()
    assert job.result == 6


@pytest.mark.parametrize('fixture', fixture_types['engine'])
def test_python_instance_method(fixture, request):
    engine = request.getfuncargvalue(fixture)
    obj = function_tests.Cls()
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
    mylist = [3, 2, 1]
    result = _runcall(fixture, request, sorted, mylist)
    assert result == [1,2,3]


@pytest.mark.parametrize('fixture', fixture_types['engine'])
def test_function_with_closure_var(fixture, request):
    result = _runcall(fixture, request, function_tests.fn_withvar, 5.0)
    assert result == 8.0


@pytest.mark.parametrize('fixture', fixture_types['engine'])
def test_function_with_closure_func(fixture, request):
    result = _runcall(fixture, request, function_tests.fn_withfunc, [1, 2], [3, 4])
    assert result == [1,2,3,4]


@pytest.mark.parametrize('fixture', fixture_types['engine'])
def test_function_with_closure_mod(fixture, request):
    od = _runcall(fixture, request, function_tests.fn_withmod, [('a', 'b'), ('c', 'd')])
    assert od.__class__.__name__ == 'OrderedDict'
    assert list(od.keys()) == ['a', 'c']
    assert list(od.values()) == ['b', 'd']


@pytest.mark.parametrize('fixture', fixture_types['engine'])
def test_function_with_renamed_closure_mod(fixture, request):
    if sys.version_info.major == 3:
        pytest.xfail("This is either impossible or a bug with Python 3")

    result = _runcall(fixture, request, function_tests.fn_with_renamed_mod)
    assert len(result) == 10
    for x in result:
        assert 0.0 <= x <= 1.0


@pytest.mark.parametrize('fixture', fixture_types['engine'])
def test_function_with_renamed_module_var(fixture, request):
    result = _runcall(fixture, request, function_tests.fn_with_renamed_attr, 'a')
    assert not result


@pytest.mark.parametrize('fixture', fixture_types['engine'])
def test_bash_exitcode(fixture, request):
    engine = request.getfuncargvalue(fixture)
    job = pyccc.Job(image='python:2.7-slim',
                    command='sleep 5 && exit 35',
                    engine=engine,
                    submit=True)
    with pytest.raises(pyccc.JobStillRunning):
        job.exitcode
    job.wait()
    assert job.wait() == 35
    assert job.exitcode == 35


@pytest.mark.parametrize('fixture', fixture_types['engine'])
def test_python_exitcode(fixture, request):
    engine = request.getfuncargvalue(fixture)
    fn = pyccc.PythonCall(function_tests.sleep_then_exit_38)
    job = engine.launch(image=PYIMAGE, command=fn, interpreter=PYVERSION)

    with pytest.raises(pyccc.JobStillRunning):
        job.exitcode

    job.wait()
    assert job.wait() == 38
    assert job.exitcode == 38


class MyRefObj(object):
    _PERSIST_REFERENCES = True

    def identity(self):
        return self

    def tagme(self):
        self.tag = 'mytag'
        return self


@pytest.mark.parametrize('fixture', fixture_types['engine'])
def test_persistence_assumptions(fixture, request):
    # Object references are not persisted across function calls by default.
    # This is the control experiment prior to the following tests
    testobj = MyRefObj()
    testobj.o = MyRefObj()
    testobj.o.o = testobj

    engine = request.getfuncargvalue(fixture)
    pycall = pyccc.PythonCall(testobj.identity)

    # First the control experiment - references are NOT persisted
    job = engine.launch(PYIMAGE, pycall, interpreter=PYVERSION)
    job.wait()
    result = job.result
    assert result is not testobj
    assert result.o is not testobj.o
    assert result.o.o is result


@pytest.mark.parametrize('fixture', fixture_types['engine'])
def test_persist_references_flag(fixture, request):
    testobj = MyRefObj()
    testobj.o = MyRefObj()
    testobj.o.o = testobj

    engine = request.getfuncargvalue(fixture)
    pycall = pyccc.PythonCall(testobj.identity)

    # With the right flag, references ARE now persisted
    job = engine.launch(PYIMAGE, pycall, interpreter=PYVERSION, persist_references=True)
    job.wait()
    result = job.result
    assert result is testobj
    assert result.o is testobj.o
    assert result.o.o is result


@pytest.mark.parametrize('fixture', fixture_types['engine'])
def test_persistent_and_nonpersistent_mixture(fixture, request):
    # References only persisted in objects that request it
    testobj = MyRefObj()
    testobj.o = MyRefObj()
    testobj.o.o = testobj
    testobj.should_persist = MyRefObj()
    testobj._PERSIST_REFERENCES = False
    testobj.o._PERSIST_REFERENCES = False

    engine = request.getfuncargvalue(fixture)
    pycall = pyccc.PythonCall(testobj.identity)

    job = engine.launch(PYIMAGE, pycall, interpreter=PYVERSION, persist_references=True)
    job.wait()
    result = job.result
    assert result is not testobj
    assert result.o is not testobj.o
    assert result.o.o is result
    assert result.should_persist is testobj.should_persist


@pytest.mark.parametrize('fixture', fixture_types['engine'])
def test_callback(fixture, request):
    def _callback(job):
        return job.get_output('out.txt').read().strip()

    engine = request.getfuncargvalue(fixture)
    job = engine.launch(image=PYIMAGE,
                        command='echo hello world > out.txt',
                        when_finished=_callback)
    job.wait()

    assert job.result == 'hello world'


@pytest.mark.parametrize('fixture', fixture_types['engine'])
def test_unicode_stdout_and_return(fixture, request):
    engine = request.getfuncargvalue(fixture)
    fn = pyccc.PythonCall(function_tests.fn_prints_unicode)
    job = engine.launch(image=PYIMAGE, command=fn, interpreter=PYVERSION)
    job.wait()
    assert job.result == u'¶'
    assert job.stdout.strip() == u'Å'
    assert job.stderr.strip() == u'µ'


@pytest.mark.parametrize('fixture', fixture_types['engine'])
def test_callback_after_python_job(fixture, request):
    def _callback(job):
        return job.function_result - 1

    fn = pyccc.PythonCall(function_tests.fn, 3.0)
    engine = request.getfuncargvalue(fixture)
    job = engine.launch(image=PYIMAGE, command=fn, interpreter=PYVERSION, when_finished=_callback)
    job.wait()

    assert job.function_result == 4.0
    assert job.result == 3.0


@pytest.mark.parametrize('fixture', fixture_types['engine'])
def test_job_with_callback_and_references(fixture, request):
    def _callback(job):
        return job.function_result.obj

    testobj = MyRefObj()
    testobj.obj = MyRefObj()

    fn = pyccc.PythonCall(testobj.tagme)
    engine = request.getfuncargvalue(fixture)
    job = engine.launch(image=PYIMAGE, command=fn,
                        interpreter=PYVERSION, when_finished=_callback, persist_references=True)
    job.wait()

    assert job.function_result is testobj
    assert job.result is testobj.obj
    assert job.function_result.obj is testobj.obj

    # A surprising result but correct behavior - because we replace the object with its reference,
    # it is unchanged.
    assert not hasattr(job.result, 'tag')
    assert not hasattr(testobj, 'tag')
    assert hasattr(job.updated_object, 'tag')


def _runcall(fixture, request, function, *args, **kwargs):
    engine = request.getfuncargvalue(fixture)
    fn = pyccc.PythonCall(function, *args, **kwargs)
    job = engine.launch(image=PYIMAGE, command=fn, interpreter=PYVERSION)
    job.wait()
    return job.result
