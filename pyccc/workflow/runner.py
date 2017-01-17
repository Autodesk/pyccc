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

    @property
    def finished(self):
        raise NotImplementedError()

    @property
    def outputs(self):
        raise NotImplementedError()


class SerialRuntimeRunner(AbstractWorkflowRunner):
    """
    Runs a workflow, serially, in this python interpreter. Not distributed in the slightest.
    """
    TaskRunner = taskrunner.TaskRuntimeRunner

    def __init__(self, workflow, **inputs):
        super(SerialRuntimeRunner, self).__init__(workflow, **inputs)
        self.tasks = {name: self.TaskRunner(task, self)
                      for name, task in self.workflow.tasks.iteritems()}
        self._outputs = None
        self._finished = False

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
                    self._prepare_inputs(task)

                if task.ready:
                    stuck = False
                    print 'Running task %s ...' % name,
                    task.run()
                    print 'done'

            if finished:
                break

            if stuck:
                raise ValueError('No tasks are ready to run ...')

        self._finished = True
        self._outputs = {fieldname: source.getvalue(self)
                         for fieldname, source in self.workflow.outputfields.iteritems()}

        return self._outputs

    @property
    def finished(self):
        return self._finished

    @property
    def outputs(self):
        return self._outputs


class SerialCCCRunner(SerialRuntimeRunner):
    TaskRunner = taskrunner.TaskCCCRunner

    def __init__(self, workflow, engine, **inputs):
        self.workflow = workflow
        self.inputs = inputs
        self.tasks = {name: self.TaskRunner(task, engine, self)
                      for name, task in self.workflow.tasks.iteritems()}

