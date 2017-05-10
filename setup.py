import sys
from setuptools import find_packages, setup
import versioneer


PACKAGE_NAME = 'pyccc'

CLASSIFIERS = """\
Development Status :: 4 - Beta
Natural Language :: English
Intended Audience :: Science/Research
Intended Audience :: Developers
License :: OSI Approved :: Apache Software License
Programming Language :: Python :: 2
Programming Language :: Python :: 2.7
Programming Language :: Python :: 3
Programming Language :: Python :: 3.5
Programming Language :: Python :: 3.6
Topic :: System :: Distributed Computing
Operating System :: POSIX
Operating System :: Unix
Operating System :: MacOS
"""

PYEXT = set('.py .pyc .pyo'.split())


with open('requirements.txt', 'r') as reqfile:
    requirements = [x.strip() for x in reqfile if x.strip()]


setup(
    name=PACKAGE_NAME,
    version=versioneer.get_version(),
    classifiers=CLASSIFIERS.splitlines(),
    packages=find_packages(),
    include_package_data=True,
    cmdclass=versioneer.get_cmdclass(),
    install_requires=requirements,
    url='http://github.com/autodesk/py-cloud-compute-cannon',
    license='Apache 2.0',
    author='Aaron Virshup and Dion Amago, BioNano Research at Autodesk',
    author_email='moleculardesigntoolkit@autodesk.com',
    description='PyCloudComputeCannon: Python bindings for CloudComputeCannon (with support for other computational '
                'engines)'
)
