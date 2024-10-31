#!/usr/bin/env bash

set -euo pipefail

cd "$(dirname "$0")"

pip install -r requirements-dev.txt

pytest
