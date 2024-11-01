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

cat > /tmp/markclipper_output

title=$(jq -r ".metadata.title" /tmp/markclipper_output)
# trim title
title=$(echo "$title" | sed 's/^\s*//; s/\s*$//;')
if [ -z "${title}" ]; then
    title=$(jq -r ".url" /tmp/markclipper_output)
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

jq -r ".content.${CONTENT_FORMAT}" /tmp/markclipper_output > "/tmp/${file_name}"

rm -f /tmp/markclipper_output

# print the file name
echo "/tmp/${file_name}"
