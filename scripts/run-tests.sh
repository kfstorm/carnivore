#!/usr/bin/env bash

set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

pytest -v -m "not live" \
  carnivore-lib/tests/test.py \
  carnivore-lib/tests/test_fetch_cache.py \
  tests/acceptance "$@"
