#!/usr/bin/env bash

set -euo pipefail

BASE_COMMIT=${1:-}
HEAD_COMMIT=${2:-HEAD}
PR_BODY=${3:-}

if [[ -z ${BASE_COMMIT} ]]; then
  echo "Usage: $0 BASE_COMMIT [HEAD_COMMIT]" >&2
  exit 2
fi
git rev-parse --verify "${BASE_COMMIT}^{commit}" >/dev/null
git rev-parse --verify "${HEAD_COMMIT}^{commit}" >/dev/null

mapfile -t changed_files < <(git diff --name-only "${BASE_COMMIT}...${HEAD_COMMIT}")
protected_files=()
initial_files=()
other_files=()

for file in "${changed_files[@]}"; do
  case ${file} in
  Dockerfile | docker/core.lock | benchmarks/corpus.yml | benchmarks/results/*.json | scripts/benchmark.py | tests/acceptance/fixture_server.py)
    if git cat-file -e "${BASE_COMMIT}:${file}" 2>/dev/null; then
      protected_files+=("${file}")
    else
      initial_files+=("${file}")
    fi
    ;;
  *)
    other_files+=("${file}")
    ;;
  esac
done

if [[ ${#protected_files[@]} -gt 0 && ${#other_files[@]} -gt 0 ]]; then
  echo "CI input changes must be submitted as a separate reviewed change." >&2
  exit 1
fi
if [[ ${#initial_files[@]} -gt 0 && ${#other_files[@]} -gt 0 &&
  ${PR_BODY} != *"CI input bootstrap:"* ]]; then
  echo "A mixed initial CI input change requires the 'CI input bootstrap:' marker." >&2
  exit 1
fi

if [[ ${#protected_files[@]} -gt 0 || ${#initial_files[@]} -gt 0 ]]; then
  rationale=${PR_BODY#*"CI input change rationale:"}
  marker_missing=false
  if [[ ${PR_BODY} == "${rationale}" ]]; then
    marker_missing=true
  fi
  rationale=${rationale//[[:space:]]/}
  if [[ ${marker_missing} == true || ${#rationale} -lt 20 ]]; then
    echo "Protected CI input changes require 'CI input change rationale:' in the PR body." >&2
    exit 1
  fi
  echo "Protected CI input change detected; require the CODEOWNER review."
fi
