

class WorkflowRunner(object):
    """
    Runs a workflow, serially, in this python interpreter. Not distributed in the slightest.
    """

    def __init__(self, workflow):
        self.workflow = workflow



class PyCCCRunner(object):


    @property
    def ready(self):
        for source in self.inputs.itervalues():
            if not source.task.done:
                return False
        else:
            return True

    @property
    def started(self):
        return self.job.status != 'queued'

    @property
    def done(self):
        if self.job is None:
            return False
        elif self.job.status == 'finished':
            return True

    def run(self, engine):
        import pyccc
        args = {name: source.getvalue() for name, source in self.inputs.iteritems()}
        self.job = engine.launchpy(image=self.image,
                                   call=pyccc.PythonCall(self.func, **args))