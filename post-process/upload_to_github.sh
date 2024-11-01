#!/usr/bin/env bash

set -euo pipefail

BASE_DIR=$(dirname "$0")

file_path=$("${BASE_DIR}/atomic/save_file.sh" markdown)
file_name=$(basename "${file_path}")

"${BASE_DIR}/atomic/github_upload.sh" "${file_path}" "${GITHUB_REPOSITORY}" "${REPOSITORY_DIR}/${file_name}"

rm -f "${file_path}"
