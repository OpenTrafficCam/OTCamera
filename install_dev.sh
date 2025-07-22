#!/bin/bash
set -e
echo "Install OTCamera development environment."

WORKING_DIR=$(pwd)
VENV="$WORKING_DIR"/venv
PIP="$VENV"/bin/pip
PRE_COMMIT="$VENV"/bin/pre-commit

bash "$WORKING_DIR"/install.sh

$PIP install -r requirements-dev.txt --no-cache-dir
$PIP install -e .
$PRE_COMMIT install --install-hooks
