#!/usr/bin/env python3
"""Generate docs/cli-mcp-reference.md for stable CLI commands and MCP tools.

Classification source: docs/plate/research/public-surface-inventory.md (#1056).
Bodies are derived from the CLI parser and plate-mcp tool schemas.

Usage (from repo root):
    python3 scripts/generate-cli-mcp-reference.py
    python3 scripts/generate-cli-mcp-reference.py --check
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SRC_ROOT = _REPO_ROOT / "src"
if str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))

from plate_core.cli_mcp_reference import (  # noqa: E402
    cli_mcp_reference_in_sync,
    write_cli_mcp_reference,
)


def main() -> int:
    check = "--check" in sys.argv[1:]
    if check:
        ok, errors = cli_mcp_reference_in_sync(_REPO_ROOT)
        if not ok:
            print("ERROR: CLI/MCP reference is out of date.", file=sys.stderr)
            for error in errors:
                print(f"  - {error}", file=sys.stderr)
            print(
                "Run `python3 scripts/generate-cli-mcp-reference.py` and commit the result.",
                file=sys.stderr,
            )
            return 1
        print("CLI/MCP reference OK (docs/cli-mcp-reference.md)")
        return 0

    path = write_cli_mcp_reference(_REPO_ROOT)
    print(f"Wrote {path.relative_to(_REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())