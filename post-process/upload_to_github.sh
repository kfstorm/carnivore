#!/usr/bin/env bash

set -euo pipefail

BASE_DIR=$(dirname "$0")

# Get the file paths from save_files.sh
file_paths=$("${BASE_DIR}/atomic/save_files.sh" "${CONTENT_FORMATS:-markdown}")

OPTIONAL_ARGS=()
if [ -n "${GITHUB_BRANCH:-}" ]; then
    OPTIONAL_ARGS+=("--branch" "${GITHUB_BRANCH}")
fi

# Iterate over each file path
echo "${file_paths}" | while IFS= read -r file_path; do
    file_name=$(basename "${file_path}")

    # Upload the file to GitHub
    python "${BASE_DIR}/atomic/github_upload.py" \
        --file-path "${file_path}" \
        --repo "${GITHUB_REPO}" \
        --repo-path "${GITHUB_REPO_DIR}/${file_name}" \
        "${OPTIONAL_ARGS[@]}"

    rm -f "${file_path}"
done
