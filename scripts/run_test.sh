#!/usr/bin/env bash

set -euo pipefail

cd "$(dirname "$0")/../app"

python main.py --url "https://clickhouse.com/blog/a-new-powerful-json-data-type-for-clickhouse" --output-dir ../data
