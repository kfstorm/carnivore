#!/usr/bin/env bash

set -euo pipefail

BASE_DIR=$(dirname "${BASH_SOURCE[0]}")
cd "${BASE_DIR}/.."

commit="HEAD"
date_arg=""
push=false

while [ $# -gt 0 ]; do
  case "$1" in
  --commit)
    if [ $# -lt 2 ]; then
      echo "Missing value for --commit" >&2
      exit 1
    fi
    commit="$2"
    shift 2
    ;;
  --date)
    if [ $# -lt 2 ]; then
      echo "Missing value for --date" >&2
      exit 1
    fi
    date_arg="$2"
    shift 2
    ;;
  --push)
    push=true
    shift
    ;;
  *)
    echo "Unknown argument: $1" >&2
    exit 1
    ;;
  esac
done

tag_date="${date_arg:-$(date +%Y-%m-%d)}"
if [[ ! ${tag_date} =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
  echo "Invalid date: ${tag_date}" >&2
  echo "Expected format YYYY-MM-DD." >&2
  exit 1
fi

tag="legacy-${tag_date}"

if ! git rev-parse --verify "${commit}^{commit}" > /dev/null 2>&1; then
  echo "Not a valid commit: ${commit}" >&2
  exit 1
fi

resolved_commit="$(git rev-parse "${commit}^{commit}")"

if git rev-parse --verify "refs/tags/${tag}" > /dev/null 2>&1; then
  echo "Tag ${tag} already exists. Refusing to overwrite an immutable tag." >&2
  exit 1
fi

if git rev-parse --verify "refs/heads/legacy" > /dev/null 2>&1; then
  echo "Branch 'legacy' already exists. The frozen branch must never be updated." >&2
  exit 1
fi

git tag -a "${tag}" -m "Legacy snapshot of old Carnivore behavior (${tag_date})" "${resolved_commit}"
git branch legacy "${resolved_commit}"

echo "Created annotated tag ${tag} and frozen branch 'legacy' at ${resolved_commit}."

if [[ ${push} == "true" ]]; then
  git push origin "${tag}" legacy
else
  echo "Push them with: git push origin ${tag} legacy"
fi
