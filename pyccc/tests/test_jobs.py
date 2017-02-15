from .engine_fixtures import *


def python_with_output_file():
    with open('my_filename.txt', 'w') as outfile:
        print >> outfile, 'some content'


@pytest.mark.parametrize('objkey', registered_types['engine'])
def test_python_job_with_output_file(objkey, request):
    engine = request.getfuncargvalue(objkey)
    pycall = pyccc.PythonCall(python_with_output_file)
    job = engine.launch('python:2.7-slim', pycall)
    job.wait()

    outputs = job.get_output()
    assert 'my_filename.txt' in outputs
    assert outputs['my_filename.txt'].read().strip() == 'some content'
    assert job.returncode == 0


@pytest.mark.parametrize('objkey', registered_types['engine'])
def test_zero_exit_code(objkey, request):
    engine = request.getfuncargvalue(objkey)
    job = engine.launch(image='python:2.7-slim',
                        command='exit 22')
    job.wait()
    assert job.returncode == 22
