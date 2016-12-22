import pickle

class _SourceData(object):
    """
    To define a workflow, SourceData-derived objects are assigned to task
    input fields to indicate where the input will be coming from
    """
    def ready(self, runner):
        """ Return true if this data is ready
        """
        raise NotImplementedError()

    def getvalue(self, runner):
        """ Return this data's value
        """

    def getpickle(self, runner):
        return pickle.dumps(self.getvalue(runner))


class _ConstantData(_SourceData):
    """ Stores predefined, constant input fields for a task
    """
    def __init__(self, value):
        self.value = value

    def ready(self, runner):
        return True

    def getvalue(self, runner):
        return self.value


class _ExternalInput(_SourceData):
    """ Placeholder for external (i.e., user) input
    """
    def __init__(self, key):
        self.key = key
        self.name = 'INPUT[%s]' % self.key

    def __repr__(self):
        return '<External input "%s">' % self.name

    def ready(self, runner):
        assert self.key in runner.inputs
        return True

    def getvalue(self, runner):
        return runner.inputs[self.key]


class _TaskOutput(_SourceData):
    """ Placeholder for a task's output field
    """

    def __init__(self, task, key):
        self.task = task
        self.key = key
        self.name = '%s[%s]' % (self.task.name, self.key)

    def __repr__(self):
        return '<Task output "%s">' % self.name

    def ready(self, runner):
        return runner.tasks[self.task.name].finished

    def getvalue(self, runner):
        taskrunner = runner.tasks[self.task.name]
        if not taskrunner.finished:
            raise ValueError('Task "%s" is not done yet' % self.task.name)
        else:
            return taskrunner.getoutput(self.key)

    def getpickle(self, runner):
        taskrunner = runner.tasks[self.task.name]
        if not taskrunner.finished:
            raise ValueError('Task "%s" is not done yet' % self.task.name)
        else:
            return taskrunner.getpickle(self.key)




class _WorkflowOutput(_SourceData):
    """ Placeholder for a worfklow's output field
    """
    def __init__(self, workflow, key):
        self.workflow = workflow
        self.key = key
        self.name = 'OUTPUT.%s' % self.key