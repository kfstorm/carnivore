#!/usr/bin/env sh

set -eu

script_dir=$(cd -- "$(dirname -- "$0")" 2>/dev/null && pwd)
exec "${script_dir}/install-carnivore-fetch.sh" --target "${HOME}/.local/bin/carnivore" "$@"
