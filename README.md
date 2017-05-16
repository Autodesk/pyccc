# py-cloud-compute-cannon
A high-level python interface for running computational jobs using a variety of distributed computing backends.

[![PyPI version](https://badge.fury.io/py/pyccc.svg)](https://badge.fury.io/py/pyccc) [ ![Codeship Status for Autodesk/py-cloud-compute-cannon](https://app.codeship.com/projects/cfce5d40-17f0-0135-533b-7a1debe13560/status?branch=master)](https://app.codeship.com/projects/218766)
## Installation

Normal installation:
`pyccc` works with Python 2.6 and 3.5+. You'll probably want a local version of [docker](https://www.docker.com/get-docker) running.

```shell
pip install pyccc
```

Dev install:
```shell
git clone https://github.com/autodesk/py-cloud-compute-cannon
pip install -e py-cloud-compute-cannon
```

## Examples

Run a job in a local subprocess:
```python
>>> engine = pyccc.Subprocess()
>>>
>>> engine.launch(command='echo hello world')
>>> engine.wait()
>>> engine.stdout
'hello world\n'
```

Run a python command on a demo cloud server, using the 'python:2.7-slim' docker image:
```python
>>> engine = pyccc.CloudComputeCannon('http://cloudcomputecannon.bionano.autodesk.com:9000')
>>>
>>> def add_one_to_it(x): return x+1
>>> cmd = pyccc.PythonCall(add_one_to_it, 5)
>>>
>>> job = engine.launch('python:2.7-slim', cmd)
>>> job.wait()
>>> job.result
6
```

## Contributing
`pyccc` is developed and maintained by the [Molecular Design Toolkit](https://github.com/autodesk/molecular-design-toolkit) project. Please see that project's [CONTRIBUTING document](https://github.com/autodesk/molecular-design-toolkit/CONTRIBUTING.md) for details.


## License

Copyright 2016 Autodesk Inc.

Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except in compliance with the License. You may obtain a copy of the License at

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the specific language governing permissions and limitations under the License.
