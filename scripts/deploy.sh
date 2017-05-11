#!/usr/bin/env bash

pip install twine
python setup.py check sdist
twine upload -u ${PYPI_USER} -p ${PYPI_PASSWORD} dist/*
