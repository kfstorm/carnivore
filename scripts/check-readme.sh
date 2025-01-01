#!/usr/bin/env bash

set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

exceptions=(
  CARNIVORE_CHROME_EXTENSION_PATHS
)

all_arguments=$(git grep -oEh 'CARNIVORE_[A-Z_]+' | sort -u)
error=0
for argument in ${all_arguments}; do
  in_exceptions=false
  for exception in "${exceptions[@]}"; do
    if [[ ${exception} == "${argument}" ]]; then
      in_exceptions=true
      break
    fi
  done
  if [[ ${in_exceptions} == true ]]; then
    continue
  fi
  if ! grep -q -- "- \`${argument}\`" README.md; then
    echo "Missing argument description in README.md: ${argument}" >&2
    error=1
  fi
done

exit ${error}
