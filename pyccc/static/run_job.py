#!/usr/bin/env python
# This is a script that drives the remote computation of a function or instance method.
# It's designed to be launched by the JobLauncher class in cloud.ipy
# The job.pkl and source.py files will be staged in.
# result.pkl (and obj_final.pkl for instance methods) file will be staged out
import cPickle as cp
import traceback as tb

if __name__ == '__main__':
    # Load any passed source libraries
    execfile('source.py')
    try:

        # Read in the packaged function
        with open('function.pkl', 'r') as pf:
            job = cp.load(pf)
        if hasattr(job, 'func_name'):
            func = globals()[job.func_name]
        else:
            func = None

        # Run the function!
        result = job.run(func)

        # Serialize the results
        with open('_function_return.pkl', 'w') as rp:
            cp.dump(result, rp, cp.HIGHEST_PROTOCOL)
        if job.is_imethod:
            with open('_object_state.pkl', 'w') as ofp:
                cp.dump(job.obj, ofp, cp.HIGHEST_PROTOCOL)

    # Catch all exceptions and return them to the client
    except Exception as exc:
        with open('exception.pkl', 'w') as excfile:
            cp.dump(exc, excfile)
        with open('traceback.txt', 'w') as tbfile:
            tb.print_exc(file=tbfile)
