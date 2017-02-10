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
import json
import pickle
import sys

import time
import traceback

import yaml

import pyccc

if pyccc.ui.widgets_enabled:
    from IPython.display import display
else:
    display = None


class AbstractTaskRunner(object):
    """ Abstract class for running tasks
    """

    def __init__(self, task, parentrunner):
        self.spec = task
        self.parentrunner = parentrunner
        self._expectedfields = set(self.spec.inputfields)

    def run(self):
        raise NotImplementedError()

    @property
    def ready(self):
        return len(self._expectedfields) == 0

    @property
    def finished(self):
        raise NotImplementedError()

    @property
    def inputs(self):
        raise NotImplementedError()

    @property
    def outputfields(self):
        raise NotImplementedError()


class MockUITask(AbstractTaskRunner):
    """ For a UI task that has completed.
    """

    finished = True
    ready = True

    def __init__(self, spec, outputs):
        self.spec = spec
        self._outputs = outputs

    def getoutput(self, field):
        return self._outputs[field]

    def getpickle(self, field):
        return pickle.dumps(self._outputs[field])

    @property
    def outputfields(self):
        return self._outputs.keys()


class TaskRuntimeRunner(AbstractTaskRunner):
    """
    Runs this task in the current interpreter
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
        start_time = time.time()
        print '\nRunning task "%s" in current runtime ...' % self.spec.name
        print '  input_fields:'
        for field, source in self.spec.inputfields.iteritems():
            print '    "%s": <%s>'%(field, source)

        self._result = self.spec(**self._inputs)
        if self._result is None:
            self._result = {}

        print 'Done with task "%s"'%self.spec.name
        print 'Total walltime for "%s": %.2f s'%(self.spec.name, time.time()-start_time)

    @property
    def inputs(self):
        if self.ready:
            return self._inputs
        else:
            raise ValueError('Inputs not connected')

    @property
    def finished(self):
        return self._result is not None

    def getoutput(self, field):
        return self._result[field]

    @property
    def outputfields(self):
        return self._result.keys()

    def getpickle(self, field):
        return pickle.dumps(self._result[field])


class TaskCCCRunner(AbstractTaskRunner):
    """
    Run a task via pyCCC
    """
    def __init__(self, task, parentrunner):
        super(TaskCCCRunner, self).__init__(task, parentrunner)
        self.job = None
        self.engine = parentrunner.engine
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
        print '\nRunning task "%s" on %s' % (self.spec.name, self.engine)
        start_time = time.time()
        funccall = pyccc.PythonCall(self.spec.func)
        funccall.separate_fields = self._inputfields
        self.job = self.engine.launch(command=funccall,
                                      image=self.spec.image,
                                      inputs=self._inputpickles,
                                      name=self.spec.name)
        try:
            self._wait_and_display_status(start_time)
            self._getoutputs()
            print 'Output fields:', ', '.join(self.outputfields)

        except Exception as e:
            self._dump_exception()
            raise e

        finally:
            if getattr(self.job, '_result_json', None):
                print '    ----- results.json -----'
                print yaml.safe_dump(self.job._result_json)
            else:
                print 'No stored result.json output.'

    def _dump_exception(self):
        print '--------- EXCEPTION DURING EXECUTION ----------------'
        traceback.print_exc()
        print

        try:
            stdout = self.job.stdout
        except Exception as printe:
            print '<ERROR accessing stdout: %s - %s>' % (printe.__class__.__name__, printe)
        else:
            print '\n------------ STDOUT -----------------'
            print stdout
            print

        try:
            stderr = self.job.stderr
        except Exception as printe:
            print '<ERROR accessing stderr: %s - %s>' % (printe.__class__.__name__, printe)
        else:
            print '------------ STDERR -----------------'
            print stderr

        if isinstance(self.job.engine, pyccc.CloudComputeCannon):
            print '\n  LAST CCC SERVER REQUEST:'
            pyccc.utils.dump_response_error(self.job.engine.proxy._last_response)
            print

    def _wait_and_display_status(self, start_time):
        if display:
            dobj = self.job.get_display_object()
            display(dobj)
            self.job.wait()
            dobj.update()
        else:
            print '  jobid: %s' % self.job.jobid
            print '  image: %s' % self.job.image
            print '  command: %s' % self.job.command
            print '  input_fields:'
            for field, source in self.spec.inputfields.iteritems():
                print '    "%s": <%s>' % (field, source)

            sys.stdout.flush()
            self.job.wait(verbose=True)
            print 'Done with task "%s"' % self.spec.name
            print 'Total walltime for "%s": %.2f s' % (self.spec.name, time.time()-start_time)
            _l = self.job.stdout.splitlines()
            if len(_l) > 0 and 'Python execution walltime:' in _l[-1]:
                print _l[-1]

    def _getoutputs(self):
        self.job.reraise_remote_exception()
        fields = self.job.get_output('outputfields.txt').read().splitlines()

        for f in fields:
            self._outputpickles[f] = self.job.get_output('outputs/%s.pkl' % f)

    @property
    def finished(self):
        return self.job is not None and self.job.status.lower() == 'finished'

    @property
    def inputs(self):
        return self._inputpickles

    def getpickle(self, field):
        return self._outputpickles[field]

    def getoutput(self, field):
        return pickle.loads(self.getpickle(field).read())

    @property
    def outputfields(self):
        return self._outputpickles.keys()
