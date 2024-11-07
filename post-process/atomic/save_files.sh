#!/usr/bin/env bash

set -euo pipefail

# This script takes the output of carnivore and choose one or more content formats to save to temp files.
#
# Environment variables:
# CARNIVORE_OUTPUT_FORMATS (optional). Options: "markdown", "html", "full_html", "rendered_html". You can provide multiple formats separated by comma. Default: "markdown"
#
# Output:
# The path to the saved file

CARNIVORE_OUTPUT_FORMATS="${CARNIVORE_OUTPUT_FORMATS:-markdown}"

temp_file=$(mktemp)
output_files=()

trap 'rm -f "${temp_file}"; rm -f "${output_files[@]}"' ERR

cat > "${temp_file}"

if title=$(jq -e -r ".metadata.title // empty" "${temp_file}"); then
  # trim title
  title=$(echo "$title" | sed -E 's/^[[:space:]]*//; s/[[:space:]]*$//;')
else
  title=$(jq -r ".metadata.url" "${temp_file}")
fi

# replace
base_file_name=$(echo "$title" | sed -E 's/[<>:"/\\|?*]/-/g; s/[[:space:]]/ /g;')
if [ -z "${base_file_name}" ]; then
  base_file_name="untitled"
fi

output_dir="${CARVIVORE_OUTPUT_DIR:-/tmp}"
mkdir -p "${output_dir}"

IFS=',' read -r -a CARNIVORE_OUTPUT_FORMATS <<< "${CARNIVORE_OUTPUT_FORMATS}"
for carnivore_output_format in "${CARNIVORE_OUTPUT_FORMATS[@]}"; do
  case "${carnivore_output_format}" in
  "markdown")
    file_name="${base_file_name}.md"
    ;;
  "html")
    file_name="${base_file_name}.html"
    ;;
  "full_html")
    file_name="${base_file_name}.full.html"
    ;;
  "rendered_html")
    file_name="${base_file_name}.rendered.html"
    ;;
  *)
    echo "Invalid output format: ${carnivore_output_format}"
    exit 1
    ;;
  esac
  output_file_path="${output_dir}/${file_name}"
  if jq -e ".content.${carnivore_output_format}" "${temp_file}" > /dev/null; then
    jq -r ".content.${carnivore_output_format}" "${temp_file}" > "${output_file_path}"
  else
    echo "Output format '${carnivore_output_format}' is not available." >&2
    continue
  fi
  if [ "${carnivore_output_format}" == "markdown" ]; then
    if [ -n "${CARNIVORE_MARKDOWN_FRONTMATTER_KEY_MAPPING:-}" ] || [ -n "${CARNIVORE_MARKDOWN_FRONTMATTER_ADDITIONAL_ARGS:-}" ]; then
      additional_args=()
      if [ -n "${CARNIVORE_MARKDOWN_FRONTMATTER_ADDITIONAL_ARGS:-}" ]; then
        read -r -a additional_args <<< "${CARNIVORE_MARKDOWN_FRONTMATTER_ADDITIONAL_ARGS}"
      fi
      python "$(dirname "$0")/frontmatter.py" \
        --metadata "$(jq -r '.metadata' "${temp_file}")" \
        --key-mapping "${CARNIVORE_MARKDOWN_FRONTMATTER_KEY_MAPPING:-}" \
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

if [ ${#output_files[@]} -eq 0 ]; then
  echo "No output files were saved." >&2
  exit 1
fi
