#!/usr/bin/env bash

cat > $HOME/.pypirc << EOF
[server-login]
username=${PYPI_USER}
password=${PYPI_PASSWORD}

EOF

python setup.py check sdist upload
