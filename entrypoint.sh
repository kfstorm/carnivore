#!/usr/bin/env bash

set -euo pipefail

if [ -z "${POST_PROCESS_COMMAND:-}" ]; then
  POST_PROCESS_COMMAND="post-process/print_metadata.sh"
fi

python telegram-bot/app/main.py \
  --token "${TELEGRAM_TOKEN}" \
  --channel-id "${TELEGRAM_CHANNEL_ID}" \
  --post-process-command "${POST_PROCESS_COMMAND}"
