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
    """ ``Workflow`` objects are used to construct and store workflow specifications.

    A workflow describes the relationship between a series of tasks,
    specifically how outputs from tasks should be used as inputs
    for subsequent tasks.

    Note that Workflow objects only _describe_ the workflow. To _run_ a workflow,
    you will use a :class:`pyccc.workflow.WorkflowRunner`-derived class.

    Args:
        name (str): name of this workflow
        metadata (workflow.Metadata): metadata object with fields to classify
           this workflow (optional)
        default_docker_image (str): run all tasks in this docker image unless
            a different image is explicitly specified
    """
    def __init__(self, name, metadata=None,
                 default_docker_image='python:2.7-slim'):
        self.name = name
        self.default_image = default_docker_image
        self.tasks = {}
        self.inputfields = {}
        self.outputfields = {}
        self.metadata = metadata
        self._preprocessor = None

    def __repr__(self):
        return 'Workflow "%s": %d inputs, %d tasks, %s outputs' % \
               (self.name, len(self.inputfields), len(self.tasks), len(self.outputfields))

    def preprocessor(self, task):
        """ TEMPORARY HACK. Define a task as the frontend preprocessor.

        The task MUST return at least these 3 fields:
           - success (bool)
           - errors (str)
           - pdbstring (str)
        """

        assert isinstance(task, Task)
        if self._preprocessor is not None:
            raise ValueError('Can only define one preprocessor per workflow.')

        self._preprocessor = task

        return task

    def task(self, func=None, image=None, taskname=None, preprocess=False, **connections):
        """ Function decorator for adding python functions to this workflow as tasks

        Args:
            image (str): docker image to run this task in (default: self.default_image)
            taskname (str): name of this task (default: function.__name__)
            preprocess (bool): flag this task as a preprocessing step
            **connections (dict): mapping from function arguments to source data

        Examples:
            >>> from pyccc.workflow import Workflow
            >>> workflow = Workflow('example')
            >>>
            >>> @workflow.task(in1=3,
            ...                in2=workflow.input('inputfield'))
            >>> def task_function(in1, in2):
            >>>     return {'out1':in1+in2,
            ...             'out2':in1-in2}
        """
        if image is None:
            image = self.default_image

        def wraptask(f):
            """ Wrapper for the :meth:`Workflow.task` decorator.

            Returns:
                Task: the Task version of the function.
            """
            if not callable(f):
                raise ValueError('"%s" is not callable and cannot be used as a task' % f)
            n = Task(f, self, image, name=taskname, **connections)
            if n.name in self.tasks:
                raise ValueError('A task named %s already exists in this workflow' % n.name)

            self.tasks[n.name] = n

            if preprocess:
                self.preprocessing.append(n)

            return n

        if func is not None:
            return wraptask(func)
        else:
            return wraptask

    def set_outputs(self, **outputs):
        """ Specify this workflow's outputs.

        Args:
            outputs (Mapping[str, data._SourceData]): mapping of output field names
               to their source data

        Examples:
            >>> workflow.set_outputs(out1=task['task_output'],
            ...                      out2=othertask['other_output'])
        """

        for fieldname, source in outputs.iteritems():
            self.outputfields[fieldname] = source

    def input(self, name):
        """ Get a reference to one of the workflow's input fields.

        Used to connect workflow inputs to task inputs.

        Examples:
            >>> @workflow.task(in1=workflow.input('workflow_input'))
            >>> def myfunction(in1):
            ...     return {'out1':in1+1}

        Args:
            name (str): the name of the input field

        Returns:
            data._ExternalInput: a reference to this input field
        """
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
    """ A ``Task`` is the basic computational unit of a workflow.

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

    Note:
        These objects will be instantiated using the :meth:`Workflow.task`
        decorator; they shouldn't be created by the user.
    """
    def __init__(self, func, workflow, image, name=None, **connections):
        self.func = func
        self.image = image
        self.name = name
        self.workflow = workflow
        if self.name is None:
            self.name = func.__name__

        self.inputfields = {}
        self.set_input_sources(**connections)

        #self.__call__.__doc__ += self.func.__doc__  # this doesn't work

    @property
    def __signature__(self):
        # hacky workaround because these objects can't be pickled or dill'd
        return funcsigs.signature(self.func)

    def __call__(self, *args, **kwargs):
        """ Calling this Task object will call the wrapped function as a normal python function.

        Its documentation is included below:
        ---------------------------------------------
        """  # docs added in __init__
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
            if inputfield not in self.__signature__.parameters:
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


