#!/usr/bin/env bash

set -euo pipefail

metadata_file=$(mktemp)

trap 'rm -f "${metadata_file}"' ERR

cat > "${metadata_file}"

if jq -e ".files.markdown" "${metadata_file}" > /dev/null; then
  markdown_file_path=$(jq -r ".files.markdown" "${metadata_file}")
  "$(dirname "$0")/atomic/add_frontmatter.sh" "${markdown_file_path}" "${metadata_file}"
fi

jq -r '.files.[]' "${metadata_file}"

rm -f "${metadata_file}"
