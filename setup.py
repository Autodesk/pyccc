import os
from os.path import relpath, join

import sys
from setuptools import find_packages, setup
import versioneer

assert sys.version_info[:2] == (2, 7), "Sorry, this package requires Python 2.7."

CLASSIFIERS = """\
Development Status :: 4 - Beta
Natural Language :: English
Intended Audience :: Science/Research
Intended Audience :: Developers
License :: OSI Approved :: Apache Software License
Programming Language :: Python :: 2.7
Programming Language :: Python :: 2 :: Only
Topic :: System :: Distributed Computing
Operating System :: POSIX
Operating System :: Unix
Operating System :: MacOS
"""

PYEXT = set('.py .pyc .pyo'.split())


with open('requirements.txt', 'r') as reqfile:
    requirements = [x.strip() for x in reqfile if x.strip()]


def find_package_data():
    files = []
    for root, dirnames, filenames in os.walk('pyccc'):
        for fn in filenames:
            basename, fext = os.path.splitext(fn)
            if fext not in PYEXT:
                files.append(relpath(join(root, fn), 'pyccc'))
    return files

setup(
    name='PyCloudComputeCannon',
    version=versioneer.get_version(),
    classifiers=CLASSIFIERS.split('\n'),
    packages=find_packages(),
    package_data={'pyccc': find_package_data()},
    cmdclass=versioneer.get_cmdclass(),
    install_requires=requirements,
    url='http://autodeskresearch.com',
    license='Apache 2.0',
    author='Aaron Virshup',
    author_email='aaron.virshup [at] autodesk [dot] com',
    description='Python bindings for CloudComputeCannon (with support for other computational '
                'engines)'
)
