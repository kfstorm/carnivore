#!/usr/bin/env bash

set -euo pipefail

cd "$(dirname "$0")"

if [[ -z ${CARNIVORE_POST_PROCESS_COMMAND:-} ]]; then
  CARNIVORE_POST_PROCESS_COMMAND="post-process/update_files.sh"
fi

if [[ -z ${CARNIVORE_APPLICATION:-} ]]; then
  CARNIVORE_APPLICATION="interactive-cli"
fi

if [[ -z ${CARNIVORE_OUTPUT_FORMATS:-} ]]; then
  export CARNIVORE_OUTPUT_FORMATS="markdown"
fi

if [[ -z ${CARNIVORE_OUTPUT_DIR:-} ]]; then
  export CARNIVORE_OUTPUT_DIR="data"
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
  --output-dir "${CARNIVORE_OUTPUT_DIR}"
)

if [[ -n ${CARNIVORE_CHROME_EXTENSION_PATHS:-} ]]; then
  args+=(--chrome-extension-paths "${CARNIVORE_CHROME_EXTENSION_PATHS}")
fi

if [[ -n ${CARNIVORE_ZENROWS_API_KEY:-} ]]; then
  args+=(--zenrows-api-key "${CARNIVORE_ZENROWS_API_KEY}")
fi

if [[ ${CARNIVORE_ZENROWS_PREMIUM_PROXIES:-} == "true" ]]; then
  args+=(--zenrows-premium-proxies)
fi

if [[ ${CARNIVORE_ZENROWS_JS_RENDERING:-} == "true" ]]; then
  args+=(--zenrows-js-rendering)
fi

if [[ ${CARNIVORE_OXYLABS_USER:-} ]]; then
  args+=(--oxylabs-user "${CARNIVORE_OXYLABS_USER}")
fi

if [[ ${CARNIVORE_OXYLABS_JS_RENDERING:-} == "true" ]]; then
  args+=(--oxylabs-js-rendering)
fi

if [[ ${CARNIVORE_APPLICATION} == "telegram-bot" ]]; then
  if [[ -n ${CARNIVORE_TELEGRAM_TOKEN:-} ]]; then
    args+=(--token "${CARNIVORE_TELEGRAM_TOKEN}")
  fi

  if [[ -n ${CARNIVORE_TELEGRAM_CHANNEL_ID:-} ]]; then
    args+=(--channel-id "${CARNIVORE_TELEGRAM_CHANNEL_ID}")
  fi
fi

python "${application_script}" "${args[@]}"
