#!/usr/bin/env bash

set -euo pipefail

# This script takes the output of markclipper and choose one content format to save to a temp file.
#
# Arguments:
# 1. content format. Options: "markdown", "html", "full_html"
#
# Output:
# The path to the saved file

CONTENT_FORMAT="${1:-}"

if [ -z "${CONTENT_FORMAT}" ]; then
    echo "CONTENT_FORMAT is not set"
    exit 1
fi

markclipper_output_path=/tmp/markclipper_output
cat > "${markclipper_output_path}"

title=$(jq -r ".metadata.title" "${markclipper_output_path}")
# trim title
title=$(echo "$title" | sed 's/^\s*//; s/\s*$//;')
if [ -z "${title}" ]; then
    title=$(jq -r ".metadata.url" "${markclipper_output_path}")
fi
# replace
file_name=$(echo "$title" | sed 's/[<>:"/\\|?*]/-/g; s/\s/ /g;')
if [ -z "${file_name}" ]; then
    file_name="untitled"
fi

case "${CONTENT_FORMAT}" in
    "markdown")
        file_name="${file_name}.md"
        ;;
    "html")
        file_name="${file_name}.html"
        ;;
    "full_html")
        file_name="${file_name}.html"
        ;;
esac

output_file_path="/tmp/${file_name}"

jq -r ".content.${CONTENT_FORMAT}" "${markclipper_output_path}" > "${output_file_path}"
if [ "${CONTENT_FORMAT}" == "markdown" ]; then
    if [ -n "${MARKDOWN_FRONTMATTER_KEY_MAPPING:-}" -o -n "${MARKDOWN_FRONTMATTER_ADDITIONAL_ARGS:-}" ]; then
        additional_args=()
        if [ -n "${MARKDOWN_FRONTMATTER_ADDITIONAL_ARGS:-}" ]; then
            additional_args=(${MARKDOWN_FRONTMATTER_ADDITIONAL_ARGS})
        fi
        python "$(dirname $0)/frontmatter.py" \
            --metadata "$(jq -r '.metadata' "${markclipper_output_path}")" \
            --key-mapping "${MARKDOWN_FRONTMATTER_KEY_MAPPING:-}" \
            "${additional_args[@]}" \
            > "${output_file_path}.tmp"
        cat "${output_file_path}" >> "${output_file_path}.tmp"
        mv "${output_file_path}.tmp" "${output_file_path}"
    fi
fi

rm -f "${markclipper_output_path}"

# print the file name
echo "${output_file_path}"
