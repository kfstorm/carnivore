#!/usr/bin/env bash

set -euo pipefail

# This script takes the output of carnivore and choose one or more content formats to save to temp files.
#
# Environment variables:
# CONTENT_FORMATS (optional). Options: "markdown", "html", "full_html". You can provide multiple formats separated by comma. Default: "markdown"
#
# Output:
# The path to the saved file

CONTENT_FORMATS="${CONTENT_FORMATS:-markdown}"

temp_file=$(mktemp)
output_files=()

trap 'rm -f "${temp_file}"; rm -f "${output_files[@]}"' ERR

cat > "${temp_file}"

title=$(jq -r ".metadata.title" "${temp_file}")
# trim title
title=$(echo "$title" | sed -E 's/^[[:space:]]*//; s/[[:space:]]*$//;')
if [ -z "${title}" ]; then
  title=$(jq -r ".metadata.url" "${temp_file}")
fi
# replace
base_file_name=$(echo "$title" | sed -E 's/[<>:"/\\|?*]/-/g; s/[[:space:]]/ /g;')
if [ -z "${base_file_name}" ]; then
  base_file_name="untitled"
fi

output_dir="${CARVIVORE_OUTPUT_DIR:-/tmp}"
mkdir -p "${output_dir}"

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
  output_file_path="${output_dir}/${file_name}"
  jq -r ".content.${content_format}" "${temp_file}" > "${output_file_path}"
  if [ "${content_format}" == "markdown" ]; then
    if [ -n "${MARKDOWN_FRONTMATTER_KEY_MAPPING:-}" ] || [ -n "${MARKDOWN_FRONTMATTER_ADDITIONAL_ARGS:-}" ]; then
      additional_args=()
      if [ -n "${MARKDOWN_FRONTMATTER_ADDITIONAL_ARGS:-}" ]; then
        read -r -a additional_args <<< "${MARKDOWN_FRONTMATTER_ADDITIONAL_ARGS}"
      fi
      python "$(dirname "$0")/frontmatter.py" \
        --metadata "$(jq -r '.metadata' "${temp_file}")" \
        --key-mapping "${MARKDOWN_FRONTMATTER_KEY_MAPPING:-}" \
        "${additional_args[@]}" \
        > "${output_file_path}.tmp"
      cat "${output_file_path}" >> "${output_file_path}.tmp"
      mv "${output_file_path}.tmp" "${output_file_path}"
    fi
  fi
  echo "${output_file_path}"
  output_files+=("${output_file_path}")
done

rm -f "${temp_file}"
