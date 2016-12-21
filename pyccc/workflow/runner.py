UNFINISHED = object()


class TaskRuntimeExecutor(object):
    """
    Runs this task here (i.e., by directly calling the functions in this runtime).
    """
    def __init__(self, task):
        self.spec = task
        self._expectedfields = set(self.spec.inputfields)
        self._inputs = {}
        self._result = None

    def connect_input(self, fieldname, value):
        if fieldname not in self._expectedfields:
            if fieldname in self._inputs:
                raise ValueError('Task %s has already received a value for field %s' %
                                 (self.spec.name, fieldname))
            else:
                raise ValueError('Task %s received an unknown input field %s' %
                                 (self.spec.name, fieldname))
        self._expectedfields.remove(fieldname)
        self._inputs[fieldname] = value

    def run(self):
        self._result = self.spec(**self._inputs)
        if self._result is None:
            self._result = {}

    @property
    def ready(self):
        return len(self._expectedfields) == 0

    @property
    def finished(self):
        return self._result is not None

    def getoutput(self, field):
        return self._result[field]


class SerialWorkflowExecutor(object):
    """
    Runs a workflow, serially, in this python interpreter. Not distributed in the slightest.
    """
    TaskExecutor = TaskRuntimeExecutor

    def __init__(self, workflow, **inputs):
        self.workflow = workflow
        self.inputs = inputs
        self.tasks = {name: self.TaskExecutor(task) for name, task in self.workflow.tasks.iteritems()}

    def prepare_inputs(self, task):
        for fieldname, source in task.spec.inputfields.iteritems():
            if source.ready(self):
                task.connect_input(fieldname, source.getvalue(self))

    def run(self):
        print 'Starting workflow "%s" with inputs %s' % (self.workflow.name, self.inputs)

        while True:
            stuck = True
            finished = True

            for name, task in self.tasks.iteritems():
                if task.finished:
                    continue

                finished = False

                if not task.ready:
                    self.prepare_inputs(task)

                if task.ready:
                    stuck = False
                    print 'Running task %s ...' % name,
                    task.run()
                    print 'done.'

            if finished:
                break

            if stuck:
                raise ValueError('No tasks are ready to run ...')

        return {fieldname: source.getvalue(self)
                for fieldname, source in self.workflow.outputfields.iteritems()}



