"""PR gate: Feature/Hardening PRs need unreleased fragments (#1182)."""

from __future__ import annotations

import argparse
import sys

from plate_core.pr_gates_checks import (
    FRAGMENT_REQUIRED_PR_TYPES,
    check_feature_release_fragment,
    normalize_label_list,
    pr_type_matches,
)

FAILURE_MARKER = "per-feature change files"


def run_gate(labels: list[str], changed_paths: list[str]) -> int:
    types = pr_type_matches(normalize_label_list(labels))
    if len(types) != 1 or types[0] not in FRAGMENT_REQUIRED_PR_TYPES:
        return 0
    failure = check_feature_release_fragment(labels, changed_paths)
    if failure is None:
        return 0
    print(
        "\n".join(
            [
                f"## ⚠️ release fragment",
                "",
                failure.message,
            ]
        ),
        file=sys.stderr,
    )
    return 1


def parse_labels(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


def _read_paths_file(path: str) -> list[str]:
    lines: list[str] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if stripped:
                lines.append(stripped)
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PLATE release fragment PR gate (#1182)")
    parser.add_argument("--labels", default="", help="Comma-separated PR labels")
    parser.add_argument(
        "--paths-file",
        required=True,
        help="Newline-separated changed file paths (non-removed)",
    )
    args = parser.parse_args(argv)
    return run_gate(parse_labels(args.labels), _read_paths_file(args.paths_file))


if __name__ == "__main__":
    raise SystemExit(main())