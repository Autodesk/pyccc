import funcsigs
from . import datasources as data


class Workflow(object):
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
        self.job = None

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


