#!/usr/bin/env sh
# PLATE pre-commit hook — format, lint, and typecheck on staged files (#1302).
# Install: gh plate hooks install --hook pre-commit
# Docs: docs/bootstrap/pre-push-hook.md
set -eu
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
if command -v gh >/dev/null 2>&1; then
  exec gh plate hooks run pre-commit
fi
exec python3 -c "import sys; from plate_core.git_hooks import run_pre_commit_hook; sys.exit(run_pre_commit_hook())"
