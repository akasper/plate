#!/usr/bin/env sh
# PLATE pre-push hook — format, lint, and typecheck on changed files (#1281).
# Install: gh plate hooks install
# Docs: docs/bootstrap/pre-push-hook.md
set -eu
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
if command -v gh >/dev/null 2>&1; then
  exec gh plate hooks run pre-push
fi
exec python3 -c "import sys; from plate_core.git_hooks import run_pre_push_from_stdin; sys.exit(run_pre_push_from_stdin())"
