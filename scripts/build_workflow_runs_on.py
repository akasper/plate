#!/usr/bin/env python3
"""Write plate-select-runs-on composite action into repo + template payload (#1214)."""

from __future__ import annotations

from pathlib import Path

from plate_core.workflow_runs_on import action_paths, composite_action_yaml

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    text = composite_action_yaml()
    for path in action_paths(ROOT):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
