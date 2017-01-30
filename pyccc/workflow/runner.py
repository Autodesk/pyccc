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
import sys

from . import datasources
from . import taskrunner


class AbstractWorkflowRunner(object):
    def __init__(self, workflow, **inputs):
        self.workflow = workflow
        self.inputs = inputs
        self._validate_inputs()

    def _validate_inputs(self):
        expected = set(self.workflow.inputfields)
        provided = set(self.inputs)

        missing = expected - provided
        extra = provided - expected

        if len(missing) > 0:
            raise ValueError('The following input fields need to be specified: %s' %
                             ','.join(missing))

        if len(extra) > 0:
            raise ValueError('The following provided input was not recognized: %s' %
                             ','.join(extra))

    def _prepare_inputs(self, task):
        """ Hooks data up to a task's input fields
        """
        for fieldname, source in task.spec.inputfields.iteritems():
            if source.ready(self):
                task.connect_input(fieldname, source)

    def run(self):
        raise NotImplementedError()

    def preprocess(self):
        """ Must run the preprocessing step (and any dependencies), then save its state
        and exit
        """
        raise NotImplementedError()

    @property
    def finished(self):
        raise NotImplementedError()

    def get_output(self, field):
        raise NotImplementedError()


class WorkflowStuck(ValueError):
    pass


class SerialRuntimeRunner(AbstractWorkflowRunner):
    """
    Runs a workflow, serially, in this python interpreter. Not distributed in the slightest.
    """
    TaskRunner = taskrunner.TaskRuntimeRunner

    def __init__(self, workflow, engine=None, **inputs):
        super(SerialRuntimeRunner, self).__init__(workflow, **inputs)
        self.tasks = {name: self.TaskRunner(task, self)
                      for name, task in self.workflow.tasks.iteritems()}
        self._outputs = None
        self._finished = False
        assert engine is None, "This runner doesn't use an engine"

    def preprocess(self):
        task = self.tasks[self.workflow._preprocessor.name]
        self.do_task(task)
        return task

    def do_task(self, task):
        """ Execute a task (along with any dependencies).
        """
        if not task.ready:  # execute any tasks this one depends on
            for inputdata in task.spec.inputfields.itervalues():
                if not isinstance(inputdata, datasources._TaskOutput):
                    continue
                subtask = self.tasks[inputdata.task.name]
                if not subtask.finished:
                    self.do_task(subtask)

            self._prepare_inputs(task)

        if not task.finished:
            self.run_task(task.spec.name, task)

    def run(self):
        print 'Starting workflow "%s"' % self.workflow.name

        while True:
            stuck = True
            finished = True

            for name, task in self.tasks.iteritems():
                if task.finished:
                    continue

                finished = False

                if not task.ready:
                    self._prepare_inputs(task)

                if task.ready:
                    stuck = False
                    self.run_task(name, task)

            if finished:
                break

            if stuck:
                raise WorkflowStuck('No tasks are ready to run ...')

        self._finished = True
        self._outputs = {fieldname: source.getvalue(self)
                         for fieldname, source in self.workflow.outputfields.iteritems()}

        return self._outputs

    def run_task(self, name, task):
        print 'Running task %s ...'%name,
        sys.stdout.flush()

        task.run()

        print 'done'
        sys.stdout.flush()

    @property
    def finished(self):
        return self._finished

    def getoutput(self, field):
        return self._outputs[field]


class SerialCCCRunner(SerialRuntimeRunner):
    TaskRunner = taskrunner.TaskCCCRunner

    def __init__(self, workflow, engine, **inputs):
        self.workflow = workflow
        self.inputs = inputs
        self.tasks = {name: self.TaskRunner(task, engine, self)
                      for name, task in self.workflow.tasks.iteritems()}


