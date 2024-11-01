#!/usr/bin/env bash

set -euo pipefail

# This script takes the output of carnivore and choose one or more content formats to save to temp files.
#
# Arguments:
# 1. content formats. Options: "markdown", "html", "full_html". You can provide multiple formats separated by comma.
#
# Output:
# The path to the saved file

CONTENT_FORMATS="${1:-}"

if [ -z "${CONTENT_FORMATS}" ]; then
  echo "Content formats is not set"
  exit 1
fi

carnivore_output_path=/tmp/carnivore_output
cat > "${carnivore_output_path}"

title=$(jq -r ".metadata.title" "${carnivore_output_path}")
# trim title
title=$(echo "$title" | sed 's/^\s*//; s/\s*$//;')
if [ -z "${title}" ]; then
  title=$(jq -r ".metadata.url" "${carnivore_output_path}")
fi
# replace
base_file_name=$(echo "$title" | sed 's/[<>:"/\\|?*]/-/g; s/\s/ /g;')
if [ -z "${base_file_name}" ]; then
  base_file_name="untitled"
fi

IFS=',' read -r -a content_formats <<< "${CONTENT_FORMATS}"
for content_format in "${content_formats[@]}"; do
  case "${content_format}" in
  "markdown")
    file_name="${base_file_name}.md"
    ;;
  "html")
    file_name="${base_file_name}.html"
    ;;
  "full_html")
    file_name="${base_file_name}.full.html"
    ;;
  *)
    echo "Invalid content format: ${content_format}"
    exit 1
    ;;
  esac
  output_file_path="/tmp/${file_name}"
  jq -r ".content.${content_format}" "${carnivore_output_path}" > "${output_file_path}"
  if [ "${content_format}" == "markdown" ]; then
    if [ -n "${MARKDOWN_FRONTMATTER_KEY_MAPPING:-}" ] || [ -n "${MARKDOWN_FRONTMATTER_ADDITIONAL_ARGS:-}" ]; then
      additional_args=()
      if [ -n "${MARKDOWN_FRONTMATTER_ADDITIONAL_ARGS:-}" ]; then
        read -r -a additional_args <<< "${MARKDOWN_FRONTMATTER_ADDITIONAL_ARGS}"
      fi
      python "$(dirname "$0")/frontmatter.py" \
        --metadata "$(jq -r '.metadata' "${carnivore_output_path}")" \
        --key-mapping "${MARKDOWN_FRONTMATTER_KEY_MAPPING:-}" \
        "${additional_args[@]}" \
        > "${output_file_path}.tmp"
      cat "${output_file_path}" >> "${output_file_path}.tmp"
      mv "${output_file_path}.tmp" "${output_file_path}"
    fi
  fi
  echo "${output_file_path}"
done

rm -f "${carnivore_output_path}"
