#!/usr/bin/env python
# This is a script that drives the remote computation of a function or instance method.
# It's designed to be launched by the JobLauncher class in cloud.ipy
# The job.pkl and source.py files will be staged in.
# result.pkl (and obj_final.pkl for instance methods) file will be staged out
import cPickle as cp
import traceback as tb
import sys

if __name__ == '__main__':
    # Load any passed source libraries
    execfile('source.py')

    # Read in the packaged function
    with open('function.pkl', 'r') as pf:
        job = cp.load(pf)
    if hasattr(job, 'func_name'):
        func = globals()[job.func_name]
    else:
        func = None

    print 'Running!'; sys.stdout.flush()
    # Run the function!
    result = job.run(func)
    print 'done Running!'; sys.stdout.flush()


    # Serialize the results
    with open('_function_return.pkl', 'w') as rp:
        cp.dump(result, rp, cp.HIGHEST_PROTOCOL)
    if job.is_imethod:
        with open('_object_state.pkl', 'w') as ofp:
            cp.dump(job.obj, ofp, cp.HIGHEST_PROTOCOL)
