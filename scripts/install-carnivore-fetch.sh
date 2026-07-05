#!/bin/sh

set -eu

wrapper_url="https://raw.githubusercontent.com/kfstorm/carnivore/main/skills/carnivore-fetch/bin/carnivore-fetch"
target_path="${HOME}/.local/bin/carnivore-fetch"
force=false

while [ $# -gt 0 ]; do
  case "$1" in
    --force)
      force=true
      shift
      ;;
    --prefix)
      if [ $# -lt 2 ]; then
        echo "Missing value for --prefix" >&2
        exit 1
      fi
      target_path="$2/carnivore-fetch"
      shift 2
      ;;
    --target)
      if [ $# -lt 2 ]; then
        echo "Missing value for --target" >&2
        exit 1
      fi
      target_path="$2"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

if [ -e "${target_path}" ] && [ "${force}" != "true" ]; then
  echo "Refusing to overwrite existing file: ${target_path}" >&2
  echo "Pass --force to overwrite it." >&2
  exit 1
fi

target_dir=$(dirname "${target_path}")
mkdir -p "${target_dir}"

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" 2> /dev/null && pwd || true)
source_path="${script_dir}/../skills/carnivore-fetch/bin/carnivore-fetch"
if [ -n "${script_dir}" ] && [ -f "${source_path}" ]; then
  cp "${source_path}" "${target_path}"
else
  curl -fsSL "${wrapper_url}" -o "${target_path}"
fi
chmod +x "${target_path}"

echo "Installed carnivore-fetch to ${target_path}"
echo "Verify with: carnivore-fetch https://example.com"
