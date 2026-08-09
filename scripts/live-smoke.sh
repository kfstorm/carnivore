#!/usr/bin/env bash

set -euo pipefail

BASE_DIR=$(dirname "${BASH_SOURCE[0]}")
PROJECT_ROOT=$(cd "${BASE_DIR}/.." && pwd)
IMAGE=${CARNIVORE_IMAGE:-ghcr.io/kfstorm/carnivore:latest}
TIMEOUT_SECONDS=${CARNIVORE_LIVE_TIMEOUT_SECONDS:-30}
EVIDENCE_PATH=${CARNIVORE_LIVE_EVIDENCE:-${RUNNER_TEMP:-/tmp}/carnivore-live-smoke.md}

usage() {
  printf 'Usage: %s [--image IMAGE] [--timeout SECONDS] [--output PATH]\n' "$0"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
  --image)
    if [[ $# -lt 2 ]]; then
      echo "Missing value for --image" >&2
      exit 2
    fi
    IMAGE=$2
    shift 2
    ;;
  --timeout)
    if [[ $# -lt 2 ]]; then
      echo "Missing value for --timeout" >&2
      exit 2
    fi
    TIMEOUT_SECONDS=$2
    shift 2
    ;;
  --output)
    if [[ $# -lt 2 ]]; then
      echo "Missing value for --output" >&2
      exit 2
    fi
    EVIDENCE_PATH=$2
    shift 2
    ;;
  -h | --help)
    usage
    exit 0
    ;;
  *)
    echo "Unknown argument: $1" >&2
    usage >&2
    exit 2
    ;;
  esac
done

if [[ ! ${TIMEOUT_SECONDS} =~ ^[1-9][0-9]*$ ]]; then
  echo "Timeout must be a positive integer." >&2
  exit 2
fi
if [[ -z ${IMAGE} ]]; then
  echo "Image must not be empty." >&2
  exit 2
fi

WRAPPER=${PROJECT_ROOT}/skills/carnivore-fetch/bin/carnivore-fetch
if [[ ! -x ${WRAPPER} ]]; then
  echo "Fetch wrapper is not executable: ${WRAPPER}" >&2
  exit 2
fi

TEMP_DIR=$(mktemp -d)
trap 'rm -rf "${TEMP_DIR}"' EXIT
mkdir -p "$(dirname "${EVIDENCE_PATH}")"

cat > "${EVIDENCE_PATH}" << EOF
# Live smoke evidence

- Image: \`${IMAGE}\`
- Attempts per page: 3
- Success timeout per attempt: ${TIMEOUT_SECONDS}s

| Page | Result | Attempts |
| --- | --- | ---: |
EOF

run_page() {
  local page_name=$1
  local url=$2
  local anchor=$3
  local output
  local attempt
  local stderr_path

  for attempt in 1 2 3; do
    stderr_path=${TEMP_DIR}/${page_name}-${attempt}.stderr
    if output=$(
      env \
        CARNIVORE_IMAGE="${IMAGE}" \
        CARNIVORE_PULL=0 \
        CARNIVORE_CACHE=0 \
        timeout --kill-after=5s "${TIMEOUT_SECONDS}s" \
        "${WRAPPER}" "${url}" --format markdown --output json \
        2> "${stderr_path}"
    ) && jq -e --arg anchor "${anchor}" \
      'try (.ok == true and (.content | contains($anchor))) catch false' \
      <<< "${output}" > /dev/null; then
      printf '| %s | passed | %s |\n' "${page_name}" "${attempt}" >> "${EVIDENCE_PATH}"
      return 0
    fi
    printf 'Live smoke page %s failed attempt %s/3.\n' "${page_name}" "${attempt}" >&2
    if [[ ${attempt} -lt 3 ]]; then
      sleep 2
    fi
  done

  printf '| %s | failed after 3 consecutive failures | 3 |\n' "${page_name}" \
    >> "${EVIDENCE_PATH}"
  return 1
}

failures=0
run_page "static" \
  "https://jhftss.github.io/A-New-Era-of-macOS-Sandbox-Escapes/" \
  "macOS Sandbox" || failures=$((failures + 1))
run_page "dynamic" \
  "https://www.rfleury.com/p/demystifying-debuggers-part-2-the" \
  "Demystifying" || failures=$((failures + 1))
run_page "wechat" \
  "https://mp.weixin.qq.com/s/koaLJvsFLkfi_j3HKIi6Dw" \
  "Rust" || failures=$((failures + 1))

if [[ -n ${GITHUB_STEP_SUMMARY:-} ]]; then
  cat "${EVIDENCE_PATH}" >> "${GITHUB_STEP_SUMMARY}"
fi

if [[ ${failures} -gt 0 ]]; then
  echo "Live smoke had ${failures} page(s) with three consecutive failures." >&2
  exit 1
fi
