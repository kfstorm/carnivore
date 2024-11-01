#!/usr/bin/env bash

set -euo pipefail

# This script uploads a file to a GitHub repository. If the file already exists, it will be updated.
#
# Arguments:
# 1. The path to the file to upload
# 2. repository. Format: owner/repo
# 3. path in the repository
#
# Environment variables:
# GITHUB_TOKEN: A GitHub token with repo access
# GITHUB_REPO_BRANCH (optional): The branch to upload the file to. Default: the repository’s default branch
#
# Output:
# The HTML URL of the uploaded file


if [ -z "${GITHUB_TOKEN:-}" ]; then
    echo "GITHUB_TOKEN is not set"
    exit 1
fi

FILE_PATH="${1:-}"
REPOSITORY="${2:-}"
REPOSITORY_PATH="${3:-}"

if [ -z "${FILE_PATH}" ]; then
    echo "FILE_PATH is not set"
    exit 1
fi

if [ -z "${REPOSITORY}" ]; then
    echo "REPOSITORY is not set"
    exit 1
fi

if [ -z "${REPOSITORY_PATH}" ]; then
    echo "REPOSITORY_PATH is not set"
    exit 1
fi

REPOSITORY_PATH=$(echo "${REPOSITORY_PATH}" | jq -Rr '@uri')
BASE64_CONTENT=$(base64 -w 0 "${FILE_PATH}")

CURL_COMMON_ARGS=(
    -fsSL
    -H "Accept: application/vnd.github+json"
    -H "Authorization: Bearer ${GITHUB_TOKEN}"
    -H "X-GitHub-Api-Version: 2022-11-28"
    "https://api.github.com/repos/${REPOSITORY}/contents/${REPOSITORY_PATH}"
)

# Fetch the sha of the existing file (if it exists)
SHA=$(curl "${CURL_COMMON_ARGS[@]}" | jq -r .sha || true)

SHA_PART=""
if [ -n "${SHA}" ]; then
    SHA_PART=", \"sha\": \"${SHA}\""
fi

BRANCH_PART=""
if [ -n "${GITHUB_REPO_BRANCH:-}" ]; then
    BRANCH_PART=", \"branch\": \"${GITHUB_REPO_BRANCH}\""
fi

# Prepare the data payload
FILE_NAME=$(basename "${FILE_PATH}")
BODY="{\"message\": \"Upload ${FILE_NAME}\", \"content\": \"${BASE64_CONTENT}\"${SHA_PART}${BRANCH_PART}}"

# Upload the file
curl "${CURL_COMMON_ARGS[@]}" -X PUT -d "${BODY}" | jq -r .content.html_url
