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

    @property
    def outputfields(self):
        return self.workflow.outputfields.keys()


class WorkflowStuck(ValueError):
    pass


class SerialRuntimeRunner(AbstractWorkflowRunner):
    """
    Runs a workflow, serially, in this python interpreter. Not distributed in the slightest.
    """
    TaskRunner = taskrunner.TaskRuntimeRunner
    InteractiveTaskRunner = taskrunner.TaskRuntimeRunner

    def __init__(self, workflow, engine=None, **inputs):
        super(SerialRuntimeRunner, self).__init__(workflow, **inputs)
        self.engine = engine

        print '\nTasks in workflow "%s":' % self.workflow.name
        self.tasks = {name: self._get_task_runner(task)
                      for name, task in self.workflow.tasks.iteritems()}
        print
        self._outputs = None
        self._finished = False
        self.test_engine()

    def test_engine(self):
        assert self.engine is None, "This runner doesn't use an engine"

    def preprocess(self):
        task = self.tasks[self.workflow._preprocessor.name]
        self.do_task(task)
        return task

    def _get_task_runner(self, task):
        print '- %s: %s' % (task.name, "Interactive" if task.interactive else "Backend")
        if task.interactive:
            return self.InteractiveTaskRunner(task, self)
        else:
            return self.TaskRunner(task, self)

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
            task.run()

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
                    task.run()

            if finished:
                break

            if stuck:
                raise WorkflowStuck('No tasks are ready to run ...')

        self._finished = True
        self._outputs = {fieldname: source.getvalue(self)
                         for fieldname, source in self.workflow.outputfields.iteritems()}

        return self._outputs

    @property
    def finished(self):
        return self._finished

    def getoutput(self, field):
        return self._outputs[field]


class SerialCCCRunner(SerialRuntimeRunner):
    TaskRunner = taskrunner.TaskCCCRunner

    def test_engine(self):
        self.engine.test_connection()



