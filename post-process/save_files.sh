#!/usr/bin/env bash

set -euo pipefail

# If the output directory is not set, use the default value "data".
export CARVIVORE_OUTPUT_DIR="${CARVIVORE_OUTPUT_DIR:-data}"

"$(dirname "$0")/atomic/save_files.sh"
