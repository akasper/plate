#!/usr/bin/env sh
# gh plate evidence — PR screenshot attach wrapper (#1051). POSIX shell entry; logic in plate_core.
set -eu

if [ -n "${PLATE_EVIDENCE_PY:-}" ]; then
  exec "${PLATE_EVIDENCE_PY}" -m plate_core.plate_evidence "$@"
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "plate_evidence: python3 is required" >&2
  exit 1
fi

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
ROOT=$(CDPATH= cd -- "${SCRIPT_DIR}/.." && pwd)
PYTHONPATH="${ROOT}/src${PYTHONPATH:+:${PYTHONPATH}}"
export PYTHONPATH
exec python3 -m plate_core.plate_evidence "$@"