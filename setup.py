import os
from os.path import relpath, join

import sys
from setuptools import find_packages, setup
import versioneer

assert sys.version_info[:2] == (2, 7), "Sorry, this package requires Python 2.7."

PACKAGE_NAME = 'pyccc'

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


def find_package_data(pkgdir):
    """ Just include all files that won't be included as package modules.
    """
    files = []
    for root, dirnames, filenames in os.walk(pkgdir):
        not_a_package = '__init__.py' not in filenames
        for fn in filenames:
            basename, fext = os.path.splitext(fn)
            if not_a_package or (fext not in PYEXT) or ('static' in fn):
                files.append(relpath(join(root, fn), pkgdir))
    return files

setup(
    name=PACKAGE_NAME,
    version=versioneer.get_version(),
    classifiers=CLASSIFIERS.splitlines(),
    packages=find_packages(),
    package_data={PACKAGE_NAME: find_package_data(PACKAGE_NAME)},
    cmdclass=versioneer.get_cmdclass(),
    install_requires=requirements,
    url='http://github.com/autodesk/py-cloud-compute-cannon',
    license='Apache 2.0',
    author='Aaron Virshup and Dion Amago, BioNano Research at Autodesk',
    author_email='moleculardesigntoolkit@autodesk.com',
    description='PyCloudComputeCannon: Python bindings for CloudComputeCannon (with support for other computational '
                'engines)'
)
