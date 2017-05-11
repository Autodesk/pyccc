#!/usr/bin/env bash

echo "[server-login]" > $HOME/.pypirc
echo "username=${PYPI_USER}" >> $HOME/.pypirc
echo "password=${PYPI_PASSWORD}" >> $HOME/.pypirc
echo >> $HOME/.pypirc

python setup.py check sdist upload
