# PYCCC
A lightweight, high-level python library for running asynchronous commands in docker containers and handling their input and output files.



[![PyPI version](https://badge.fury.io/py/pyccc.svg)](https://badge.fury.io/py/pyccc) [ ![Codeship Status for Autodesk/py-cloud-compute-cannon](https://app.codeship.com/projects/cfce5d40-17f0-0135-533b-7a1debe13560/status?branch=master)](https://app.codeship.com/projects/218766)

#### What does the "CCC" stand for?

Nothing currently! It originally stood for [Cloud Compute Cannon](https://github.com/Autodesk/cloud-compute-cannon), which this project originally contained bindings for.


## Installation

Normal installation:
`pyccc` works with Python 2.7 and 3.5+. In normal operation, it also requires a local version of [docker](https://www.docker.com/get-docker) running.

```shell
pip install pyccc
```

Dev install:
```shell
git clone https://github.com/autodesk/py-cloud-compute-cannon
pip install -e py-cloud-compute-cannon
```

## Examples

Run an executable in a docker container:
```python
>>> engine = pyccc.engines.Docker()
>>> job = engine.launch(image='alpine',
                        command='echo hello world')
>>> job.wait()
>>> job.stdout
'hello world\n'
>>> job.exitcode
0
```


Call a python function *inside* a docker container and return the result:
```python
>>> engine = pyccc.engines.Docker()
>>> def add_one_to_it(x):
...    return x+1
>>> job = engine.launch(command=pyccc.PythonCall(add_one_to_it, 5),
...                     image='python:3.6-alpine')
>>> job.wait()
>>> job.result
6
```

## Documentation

Currently, whatever documentation exists, exists only in docstrings.

For Job options, see `pyccc.Job.__doc__`.

## Contributing
`pyccc` is developed and maintained by the [Molecular Design Toolkit](https://github.com/autodesk/molecular-design-toolkit) project. Please see that project's [CONTRIBUTING document](https://github.com/autodesk/molecular-design-toolkit/CONTRIBUTING.md) for details.


## License

Copyright 2016-2018 Autodesk Inc.

Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except in compliance with the License. You may obtain a copy of the License at

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the specific language governing permissions and limitations under the License.
