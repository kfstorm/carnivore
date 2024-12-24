#!/usr/bin/env bash

set -euo pipefail

# This script adds frontmatter to the markdown file.
#
# Arguments:
# $1: The path to the markdown file.
# $2: The path to the metadata file.
#
# Environment variables:
# CARNIVORE_MARKDOWN_FRONTMATTER_KEY_MAPPING: TODO
# CARNIVORE_MARKDOWN_FRONTMATTER_ADDITIONAL_ARGS: TODO
#
# Output:
# None

if [ -n "${CARNIVORE_MARKDOWN_FRONTMATTER_KEY_MAPPING:-}" ] || [ -n "${CARNIVORE_MARKDOWN_FRONTMATTER_ADDITIONAL_ARGS:-}" ]; then
  additional_args=()
  if [ -n "${CARNIVORE_MARKDOWN_FRONTMATTER_ADDITIONAL_ARGS:-}" ]; then
    read -r -a additional_args <<< "${CARNIVORE_MARKDOWN_FRONTMATTER_ADDITIONAL_ARGS}"
  fi
  python "$(dirname "$0")/frontmatter.py" \
    --metadata "$(jq -r '.metadata' "$2")" \
    --key-mapping "${CARNIVORE_MARKDOWN_FRONTMATTER_KEY_MAPPING:-}" \
    "${additional_args[@]}" \
    > "$1.tmp"
  cat "$1" >> "$1.tmp"
  mv "$1.tmp" "$1"
fi
