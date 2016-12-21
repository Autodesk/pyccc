import funcsigs
import pyccc


class Workflow(object):
    def __init__(self, name, default_docker_image='python:2.7-slim'):
        self.name = name
        self.default_image = default_docker_image
        self.tasks = {}
        self.runningjobs = {}
        self.finishedjobs = {}
        self.inputs = {}

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

    def input(self, name):
        if name not in self.inputs:
            self.inputs[name] = _ExternalInput(name)
        return self.inputs[name]

    def edges(self):
        edges = {}
        for name, task in self.tasks.iteritems():
            for fieldname, inputsource in task.inputs.iteritems():
                edges.setdefault(inputsource.name, []).append('%s.%s' % (task.name, fieldname))

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
        self.inputs = {}
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
        return "Task %s, inputs: %s" % (self.name, self.inputs.keys())

    def set_input_sources(self, force=False, **connections):
        """ Set the inputs for this task's arguments

        Args:
            **connections (Mapping[str, _SourceData]): mapping of inputs names to source data
            force (bool): overwrite existing connections
        """
        for inputfield, source in connections.iteritems():
            if inputfield not in self.signature.parameters:
                raise ValueError('"%s" is not an argument of %s' % (inputfield, self.name))
            if inputfield in self.inputs and not force:
                raise ValueError('Input field "%s" is already set for task %s' % (inputfield, self.name))

            self.inputs[inputfield] = source

    def __getitem__(self, item):
        """ Returns an _TaskOutput object, representing a named output of this task.

        Note that these are currently not verified (unlike inputs, which are determined by
        the function's call signature.
        """
        return _TaskOutput(self, item)


class _SourceData(object):
    pass


class _ExternalInput(_SourceData):
    """ An object representing input that will be passed from beyond the current
     workflow's scope, (e.g., as user input).

    This functions more as a flag than as a functional object.
    """
    def __init__(self, name):
        self.name = 'INPUT[%s]' % name

    def __repr__(self):
        return '<External input "%s">' % self.name


class _TaskOutput(_SourceData):
    """ A reference to a named output of a task (for internal use)
    """

    def __init__(self, task, key):
        self.task = task
        self.key = key
        self.name = '%s[%s]>' % (self.task.name, self.key)

    def __repr__(self):
        return '<Task output %s>' % self.name

    def getvalue(self):
        if not self.task.finished:
            raise pyccc.JobStillRunning()
        else:
            return self.task.getretresult(self.key)