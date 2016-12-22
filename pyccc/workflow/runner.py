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

import pickle
import pyccc


class TaskRunner(object):
    def __init__(self, task, parentrunner):
        self.spec = task
        self.parentrunner = parentrunner
        self._expectedfields = set(self.spec.inputfields)

    @property
    def ready(self):
        return len(self._expectedfields) == 0


class TaskRuntimeRunner(TaskRunner):
    """
    Runs this task here (i.e., by directly calling the functions in this runtime).
    """
    def __init__(self, task, parentrunner):
        super(TaskRuntimeRunner, self).__init__(task, parentrunner)
        self._inputs = {}
        self._result = None

    def connect_input(self, fieldname, source):
        if fieldname not in self._expectedfields and fieldname not in self._inputs:
            raise ValueError('Task "%s" received an unknown input field "%s"' %
                             (self.spec.name, fieldname))
        elif fieldname not in self._expectedfields:
            return
        self._expectedfields.remove(fieldname)
        self._inputs[fieldname] = source.getvalue(self.parentrunner)

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


class TaskCCCRunner(TaskRunner):
    """
    Run a workflow SERIALLY with CCC computes.
    """
    def __init__(self, task, engine, parentrunner):
        super(TaskCCCRunner, self).__init__(task, parentrunner)
        self.job = None
        self.engine = engine
        self._inputpickles = {}
        self._outputpickles = {}
        self._inputfields = []

    def connect_input(self, fieldname, source):
        if fieldname not in self._expectedfields and fieldname not in self._inputfields:
            raise ValueError('Task "%s" received an unknown input field "%s"' %
                             (self.spec.name, fieldname))
        elif fieldname not in self._expectedfields:
            return
        self._expectedfields.remove(fieldname)
        self._inputfields.append(fieldname)
        self._inputpickles['inputs/%s.pkl' % fieldname] = source.getpickle(self.parentrunner)

    def run(self):
        funccall = pyccc.PythonCall(self.spec.func)
        funccall.separate_fields = self._inputfields
        self.job = self.engine.launch(command=funccall,
                                      image=self.spec.image,
                                      inputs=self._inputpickles)
        self.job.wait()
        self._getoutputs()

    def _getoutputs(self):
        fields = self.job.get_output('outputfields.txt').read().splitlines()

        for f in fields:
            self._outputpickles[f] = self.job.get_output('outputs/%s.pkl' % f)

    @property
    def finished(self):
        return self.job is not None and self.job.status.lower() == 'finished'

    def getpickle(self, field):
        return self._outputpickles[field]

    def getoutput(self, field):
        return pickle.loads(self.getpickle(field).read())


class SerialRunner(object):
    """
    Runs a workflow, serially, in this python interpreter. Not distributed in the slightest.
    """
    TaskExecutor = TaskRuntimeRunner

    def __init__(self, workflow, **inputs):
        self.workflow = workflow
        self.inputs = inputs
        self.tasks = {name: self.TaskExecutor(task, self)
                      for name, task in self.workflow.tasks.iteritems()}

    def prepare_inputs(self, task):
        for fieldname, source in task.spec.inputfields.iteritems():
            if source.ready(self):
                task.connect_input(fieldname, source)

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
                    print 'done'

            if finished:
                break

            if stuck:
                raise ValueError('No tasks are ready to run ...')

        return {fieldname: source.getvalue(self)
                for fieldname, source in self.workflow.outputfields.iteritems()}


class SerialCCCRunner(SerialRunner):
    TaskExecutor = TaskCCCRunner

    def __init__(self, workflow, engine, **inputs):
        self.workflow = workflow
        self.inputs = inputs
        self.tasks = {name: self.TaskExecutor(task, engine, self)
                      for name, task in self.workflow.tasks.iteritems()}

