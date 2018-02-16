from setuptools import find_packages, setup
import subprocess
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

try:
    long_description = subprocess.check_output('pandoc --from=markdown --to=rst README.md'.split())
except subprocess.CalledProcessError:
    print('Failed to execute pandoc: long_description field not generated')
    long_description = 'missing'

setup(
    name=PACKAGE_NAME,
    version=versioneer.get_version(),
    classifiers=CLASSIFIERS.splitlines(),
    packages=find_packages(),
    include_package_data=True,
    cmdclass=versioneer.get_cmdclass(),
    install_requires=requirements,
    setup_requires=['pandoc'],
    url='http://github.com/autodesk/py-cloud-compute-cannon',
    license='Apache 2.0',
    long_description=long_description,
    author='Aaron Virshup and Dion Amago, Autodesk Life Sciences',
    author_email='moleculardesigntoolkit@autodesk.com',
    description='Library for managing docker container jobs and input/output files)'
)
