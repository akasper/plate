#!/usr/bin/env python3
"""Regenerate tests/fixtures/public_surface_stable.json from inventory + live code (#1058)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "public_surface_stable.json"

sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "tests"))
from public_surface_contract_lib import build_stable_snapshot  # noqa: E402
# Live surfaces load via plate_core.public_surface_loader inside build_stable_snapshot.


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero when the fixture differs from a freshly built snapshot.",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write tests/fixtures/public_surface_stable.json (default when neither flag is set).",
    )
    parser.add_argument(
        "--inventory",
        type=Path,
        default=None,
        help="Optional alternate inventory markdown path.",
    )
    args = parser.parse_args()
    do_write = args.write or not args.check

    built = build_stable_snapshot(inventory_path=args.inventory)
    if do_write:
        FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE_PATH.write_text(json.dumps(built, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"Wrote {FIXTURE_PATH}")
        return 0

    if not FIXTURE_PATH.is_file():
        print(f"Missing fixture: {FIXTURE_PATH} (run without --check to generate)", file=sys.stderr)
        return 1

    existing = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    if existing == built:
        print("public_surface_stable.json is up to date")
        return 0

    print("public_surface_stable.json is stale; run scripts/regenerate_public_surface_stable.py", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())