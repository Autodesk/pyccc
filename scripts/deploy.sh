#!/usr/bin/env bash

python setup.py check sdist upload --password ${PYPI_PASSWORD} --username ${PYPI_USER}
