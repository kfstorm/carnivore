#!/usr/bin/env bash

set -euo pipefail

if [[ -z ${POST_PROCESS_COMMAND:-} ]]; then
  POST_PROCESS_COMMAND="post-process/save_files.sh"
fi

if [[ -z ${INGEST_TOOL:-} ]]; then
  INGEST_TOOL="interactive-cli"
fi

python_entrypoint="${INGEST_TOOL}/app/main.py"

if [[ ! -e ${python_entrypoint} ]]; then
  echo "Invalid INGEST_TOOL: ${INGEST_TOOL}" >&2
  exit 1
fi

args=(
  --post-process-command "${POST_PROCESS_COMMAND}"
)

if [[ ${INGEST_TOOL} == "telegram-bot" ]]; then
  if [[ -n ${TELEGRAM_TOKEN:-} ]]; then
    args+=(--token "${TELEGRAM_TOKEN}")
  fi

  if [[ -n ${TELEGRAM_CHANNEL_ID:-} ]]; then
    args+=(--channel-id "${TELEGRAM_CHANNEL_ID}")
  fi
fi

ROOT_DIR="$(dirname "$0")"
export PYTHONPATH="${PYTHONPATH:-}:${ROOT_DIR}"
python "${python_entrypoint}" "${args[@]}"
