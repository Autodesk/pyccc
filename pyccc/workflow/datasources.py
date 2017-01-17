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
        assert self.key in runner.inputs, "ERROR: external input %s not present" % self.key
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