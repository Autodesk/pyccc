# Copyright 2016 Autodesk Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import funcsigs
from . import datasources as data


class Workflow(object):
    """ This object holds a workflow specification.

    A workflow describes the relationship between a series of tasks,
    specifically how outputs from an early task should be used as input
    fields for later tasks.

    Note that Workflow objects only specify these relationships; they
    do NOT describe an actual running workflow. To run a workflow,
    a WorkflowRunner subclass should be used to run a specific instance
    of a workflow on a computing backend.
    """

    def __init__(self, name, default_docker_image='python:2.7-slim'):
        self.name = name
        self.default_image = default_docker_image
        self.tasks = {}
        self.inputfields = {}
        self.outputfields = {}

    def __repr__(self):
        return "Workflow %s: %d tasks" % (self.name, len(self.tasks))

    def task(self, func=None, image=None, taskname=None, **connections):
        if image is None:
            image = self.default_image

        def wraptask(f):
            assert callable(f)
            n = Task(f, self, image, name=taskname, **connections)

            if n.name in self.tasks:
                raise ValueError('A task named %s already exists in this workflow' % n.name)

            self.tasks[n.name] = n
            return n

        if func is not None:
            return wraptask(func)
        else:
            return wraptask

    def set_outputs(self, **outputs):
        for fieldname, source in outputs.iteritems():
            self.outputfields[fieldname] = source

    def input(self, name):
        if name not in self.inputfields:
            self.inputfields[name] = data._ExternalInput(name)
        return self.inputfields[name]

    def edges(self):
        """
        Returns:
            Mapping[str, str]: dict of the form {'source1': 'target1', ...}
        """
        edges = {}
        for name, task in self.tasks.iteritems():
            for fieldname, inputsource in task.inputfields.iteritems():
                edges.setdefault(inputsource.name, []).append('%s.%s' % (task.name, fieldname))

        for name, source in self.outputfields.iteritems():
            edges.setdefault(source.name, []).append('%s.%s' % ('OUTPUT', name))

        return edges


class Task(object):
    """ A Task is the basic computational unit of a workflow.

    Each task has a series of input and output fields. A task is ready
    to run when all of its input fields have been supplied with data.

    Input fields generally get data from:
      1) Workflow input,
      2) output from another Task, or
      3) as a constant parameter in the Workflow definition.

    Note that these objects are only used to DESCRIBE a workflow -
    they don't RUN anything. For debugging convenience, however,
    a task can be executed in python by calling it, and passing values
    for its input fields as keyword arguments.
    """

    def __init__(self, func, workflow, image, name=None, **connections):
        self.func = func
        self.image = image
        self.name = name
        self.workflow = workflow
        if self.name is None:
            self.name = func.__name__

        self.signature = funcsigs.signature(func)
        self.inputfields = {}
        self.set_input_sources(**connections)

    def __call__(self, *args, **kwargs):
        """ Calling this object will call the wrapped function as normal
        """
        return self.func(*args, **kwargs)

    def __repr__(self):
        return "<Task %s (wraps function %s.%s>" % \
               (self.name, self.func.__module__, self.func.__name__)

    def __str__(self):
        return "Task %s, inputs: %s" % (self.name, self.inputfields.keys())

    def set_input_sources(self, force=False, **connections):
        """ Set the inputs for this task's arguments

        Args:
            **connections (Mapping[str, _SourceData]): mapping of inputs names to source data
            force (bool): overwrite existing connections
        """
        for inputfield, source in connections.iteritems():
            if inputfield not in self.signature.parameters:
                raise ValueError('"%s" is not an argument of %s' %
                                 (inputfield, self.name))
            if inputfield in self.inputfields and not force:
                raise ValueError('Input field "%s" is already set for task %s' %
                                 (inputfield, self.name))
            if not isinstance(source, data._SourceData):
                source = data._ConstantData(source)

            self.inputfields[inputfield] = source

    def __getitem__(self, item):
        """ Returns an _TaskOutput object, representing a named output of this task.

        Note that these are currently not verified (unlike inputs, which are determined by
        the function's call signature.
        """
        return data._TaskOutput(self, item)


