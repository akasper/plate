#!/usr/bin/env python3
"""Generate plugin AGENTS.md and per-role .agent.md files from the baseline catalog.

The baseline catalog (`src/plate_core/data/baseline_catalog.yml`) is the only
editable source. This script writes deterministic outputs to both plugin
surfaces (`plugin/` and `.plugin/`) and is gated in CI via `--check`.

Usage (from repo root):
    python3 scripts/generate-plugin-agents.py
    python3 scripts/generate-plugin-agents.py --check
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SRC_ROOT = _REPO_ROOT / "src"
if str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))

from plate_core.agents_surface import (  # noqa: E402
    plugin_agents_surfaces_in_sync,
    write_plugin_agents_surfaces,
)


def main() -> int:
    check = "--check" in sys.argv[1:]
    if check:
        ok, errors = plugin_agents_surfaces_in_sync(_REPO_ROOT)
        if not ok:
            print("ERROR: plugin agent surfaces are out of date.", file=sys.stderr)
            for error in errors:
                print(f"  - {error}", file=sys.stderr)
            print(
                "Run `python3 scripts/generate-plugin-agents.py` and commit the result.",
                file=sys.stderr,
            )
            return 1
        print("Plugin agent surfaces OK (plugin/ + .plugin/)")
        return 0

    result = write_plugin_agents_surfaces(_REPO_ROOT)
    print(f"Wrote {len(result.written_paths)} generated agent surface file(s)")
    if result.removed_paths:
        print(f"Removed {len(result.removed_paths)} stale agent file(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
