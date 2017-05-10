#!/usr/bin/env python
""" This script builds and runs automated tests for a new moldesign release.
It's manual for now, will be replaced by Travis or Jenkins soon.

You shouldn't run this unless you know exactly what you're doing and why you're doing it
"""

import os
import sys
import subprocess
import atexit

version = sys.argv[1]


def run(cmd, display=True):
    print '\n>>> %s' % cmd
    if display:
        return subprocess.check_call(cmd, shell=True)
    else:
        return subprocess.check_output(cmd, shell=True)


tags = set(run('git tag --list', display=False).splitlines())
rootdir = run('git rev-parse --show-toplevel', display=False).strip()

assert os.path.abspath(rootdir) == os.path.abspath(os.path.curdir), \
    "This command must be run at root of the repository directory"

# check that tag is valid
assert version not in tags, "Tag %s already exists!" % version
major, minor, patch = map(int, version.split('.'))


# Set the tag!
run('git tag %s' % version)
print 'Tag set: %s' % version


def untag():
    if not untag.success:
        print 'Failed. Removing version tag %s' % version
        run('git tag -d %s' % version)

untag.success = False

atexit.register(untag)

# Check that it propagated to the python package
import pyccc
assert os.path.abspath(os.path.join(pyccc.__path__[0],'..')) == os.path.abspath(rootdir)
assert pyccc.__version__ == version, 'Package has incorrect version: %s' % pyccc.__version__

untag.success = True

# This is the irreversible part - so do it manually
print """
This LOOKS ready for release! Do the following to create version %s.
If you're ready, run these commands:
1. python setup.py register -r pypi
2. python setup.py sdist upload -r pypi
3. git push origin master --tags

Finally, mark it as release "v%s" in GitHub.

TO ABORT, RUN:
git tag -d %s
""" % (version, version, version)

