#!/usr/bin/env bash

set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

rm -f .git/hooks/pre-commit
ln -s ../../scripts/hooks/pre-commit .git/hooks/pre-commit
# Avoid using the global git hooks
git config --local core.hooksPath "$(pwd)/.git/hooks"
