#!/usr/bin/env bash

set -euo pipefail

# Make sure shfmt and shellcheck command is available.
if ! command -v shfmt > /dev/null; then
  echo "Please install shfmt."
  exit 1
fi
if ! command -v shellcheck > /dev/null; then
  echo "Please install shellcheck."
  exit 1
fi

shfmt_args=(--indent 2 -sr --simplify)

# read the `--check` arg from the command line
check=false
if [ $# -gt 0 ] && [[ $1 == "--check" ]]; then
  shfmt_args+=(--diff)
  check=true
else
  shfmt_args+=(--write)
fi
if [ $# -gt 0 ] && [[ $1 == "--check" ]]; then
  shfmt_args+=(--diff)
else
  shfmt_args+=(--write)
fi

cd "$(dirname "${BASH_SOURCE[0]}")/.."

count=0
for item in $(git ls-files | grep '\.sh$'); do
  # Find basic format issues
  shfmt "${shfmt_args[@]}" "$item"

  # Find more format issues
  if [[ $check == "false" ]]; then
    if ! shellcheck "$item" > /dev/null; then
      echo "$item: fixing...."
      if ! shellcheck -f diff "$item" &> /dev/null; then
        echo "$item: failed to fix. Please fix it manually."
        shellcheck "$item"
      else
        shellcheck -f diff "$item" | git apply
      fi
    fi
  else
    shellcheck "$item"
  fi
  count=$((count + 1))
done

echo "Checked $count shell scripts."
