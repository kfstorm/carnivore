#!/usr/bin/env bash

set -euo pipefail

BASE_DIR=$(dirname "${BASH_SOURCE[0]}")

echo "Running shell scripts format..."
"${BASE_DIR}/format-shell.sh" "$@"

echo "Running Python scripts format..."
"${BASE_DIR}/format-python.sh" "$@"

echo "Checking readme..."
"${BASE_DIR}/check-readme.sh"
