#!/usr/bin/env bash

set -euo pipefail

cd "$(dirname "$0")"

if [[ -z ${CARNIVORE_POST_PROCESS_COMMAND:-} ]]; then
  CARNIVORE_POST_PROCESS_COMMAND="post-process/save_files.sh"
fi

if [[ -z ${CARNIVORE_APPLICATION:-} ]]; then
  CARNIVORE_APPLICATION="interactive-cli"
fi

if [[ -z ${CARNIVORE_OUTPUT_FORMATS:-} ]]; then
  export CARNIVORE_OUTPUT_FORMATS="markdown"
fi

application_script="applications/${CARNIVORE_APPLICATION}/main.py"

if [[ ! -e ${application_script} ]]; then
  echo "Invalid Carnivore application: ${CARNIVORE_APPLICATION}" >&2
  echo "Valid options are: $(find applications -maxdepth 1 -mindepth 1 -print0 | xargs -0 -n 1 basename | xargs)" >&2
  exit 1
fi

args=(
  --post-process-command "${CARNIVORE_POST_PROCESS_COMMAND}"
  --output-formats "${CARNIVORE_OUTPUT_FORMATS}"
)

if [[ ${CARNIVORE_APPLICATION} == "telegram-bot" ]]; then
  if [[ -n ${CARNIVORE_TELEGRAM_TOKEN:-} ]]; then
    args+=(--token "${CARNIVORE_TELEGRAM_TOKEN}")
  fi

  if [[ -n ${CARNIVORE_TELEGRAM_CHANNEL_ID:-} ]]; then
    args+=(--channel-id "${CARNIVORE_TELEGRAM_CHANNEL_ID}")
  fi
fi

python "${application_script}" "${args[@]}"
