#!/usr/bin/env bash

set -euo pipefail

cd "$(dirname "$0")"

if [[ -z ${POST_PROCESS_COMMAND:-} ]]; then
  POST_PROCESS_COMMAND="post-process/save_files.sh"
fi

if [[ -z ${CARNIVORE_APPLICATION:-} ]]; then
  CARNIVORE_APPLICATION="interactive-cli"
fi

application_script="applications/${CARNIVORE_APPLICATION}/app/main.py"

if [[ ! -e ${application_script} ]]; then
  echo "Invalid Carnivore application: ${CARNIVORE_APPLICATION}" >&2
  echo "Valid options are: $(find applications -maxdepth 1 -mindepth 1 -print0 | xargs -0 -n 1 basename | xargs)" >&2
  exit 1
fi

args=(
  --post-process-command "${POST_PROCESS_COMMAND}"
)

if [[ ${CARNIVORE_APPLICATION} == "telegram-bot" ]]; then
  if [[ -n ${TELEGRAM_TOKEN:-} ]]; then
    args+=(--token "${TELEGRAM_TOKEN}")
  fi

  if [[ -n ${TELEGRAM_CHANNEL_ID:-} ]]; then
    args+=(--channel-id "${TELEGRAM_CHANNEL_ID}")
  fi
fi

ROOT_DIR="$(dirname "$0")"
export PYTHONPATH="${PYTHONPATH:-}:${ROOT_DIR}"
python "${application_script}" "${args[@]}"
