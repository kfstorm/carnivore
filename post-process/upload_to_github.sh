#!/usr/bin/env bash

set -euo pipefail

BASE_DIR=$(dirname "$0")

if [[ -z ${CARNIVORE_GITHUB_TOKEN:-} ]]; then
  echo "CARNIVORE_GITHUB_TOKEN is required" >&2
  exit 1
fi

if [[ -z ${CARNIVORE_GITHUB_REPO:-} ]]; then
  echo "CARNIVORE_GITHUB_REPO is required" >&2
  exit 1
fi

if [[ -z ${CARNIVORE_GITHUB_REPO_DIR:-} ]]; then
  echo "CARNIVORE_GITHUB_REPO_DIR is required" >&2
  exit 1
fi

# Get the file paths from update_files.sh
file_paths=$("${BASE_DIR}/update_files.sh")

OPTIONAL_ARGS=()
if [ -n "${CARNIVORE_GITHUB_BRANCH:-}" ]; then
  OPTIONAL_ARGS+=("--branch" "${CARNIVORE_GITHUB_BRANCH}")
fi

# Iterate over each file path
echo "${file_paths}" | while IFS= read -r file_path; do
  file_name=$(basename "${file_path}")

  # Upload the file to GitHub
  python "${BASE_DIR}/atomic/github_upload.py" \
    --file-path "${file_path}" \
    --token "${CARNIVORE_GITHUB_TOKEN}" \
    --repo "${CARNIVORE_GITHUB_REPO}" \
    --repo-path "${CARNIVORE_GITHUB_REPO_DIR}/${file_name}" \
    "${OPTIONAL_ARGS[@]}"

  rm -f "${file_path}"
done
