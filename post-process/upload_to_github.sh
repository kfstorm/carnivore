#!/usr/bin/env bash

set -euo pipefail

BASE_DIR=$(dirname "$0")

file_path=$("${BASE_DIR}/atomic/save_file.sh" markdown)
file_name=$(basename "${file_path}")

OPTIONAL_ARGS=()
if [ -n "${GITHUB_BRANCH:-}" ]; then
  OPTIONAL_ARGS+=("--branch" "${GITHUB_BRANCH}")
fi

python "${BASE_DIR}/atomic/github_upload.py" \
    --file-path "${file_path}" \
    --repo "${GITHUB_REPO}" \
    --repo-path "${GITHUB_REPO_DIR}/${file_name}" \
    "${OPTIONAL_ARGS[@]}"

rm -f "${file_path}"
