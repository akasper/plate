"""PR gate: Feature/Hardening PRs need unreleased fragments (#1182)."""

from __future__ import annotations

import argparse
import sys

from plate_core.pr_gate_paths import active_paths_from_entries, parse_scope_tsv, scope_paths_from_entries
from plate_core.pr_gates_checks import (
    FRAGMENT_REQUIRED_PR_TYPES,
    check_feature_release_fragment,
    check_pr_type_labels,
    normalize_label_list,
    pr_type_matches,
)

FAILURE_MARKER = "per-feature change files"


def run_gate(labels: list[str], scope_paths: list[str], *, active_paths: list[str]) -> int:
    labels_norm = normalize_label_list(labels)
    type_failure = check_pr_type_labels(labels_norm)
    if type_failure is not None:
        print(
            "\n".join(["## ⚠️ release fragment", "", type_failure.message]),
            file=sys.stderr,
        )
        return 1
    matches = pr_type_matches(labels_norm)
    if len(matches) != 1 or matches[0] not in FRAGMENT_REQUIRED_PR_TYPES:
        return 0
    failure = check_feature_release_fragment(
        labels_norm, scope_paths, active_paths=active_paths
    )
    if failure is None:
        return 0
    print(
        "\n".join(
            [
                "## ⚠️ release fragment",
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


def _read_text_file(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PLATE release fragment PR gate (#1182)")
    parser.add_argument("--labels", default="", help="Comma-separated PR labels")
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument(
        "--scope-paths-file",
        help="TSV of filename and status (includes removed paths)",
    )
    scope.add_argument(
        "--paths-file",
        help="Legacy newline-separated paths (treated as scope and active)",
    )
    parser.add_argument(
        "--active-paths-file",
        help="Newline-separated non-removed paths (default: derive from scope TSV)",
    )
    args = parser.parse_args(argv)
    if args.scope_paths_file:
        entries = parse_scope_tsv(_read_text_file(args.scope_paths_file))
        scope_paths = scope_paths_from_entries(entries)
        if args.active_paths_file:
            active_paths = [
                line.strip()
                for line in _read_text_file(args.active_paths_file).splitlines()
                if line.strip()
            ]
        else:
            active_paths = active_paths_from_entries(entries)
    else:
        legacy = [
            line.strip()
            for line in _read_text_file(args.paths_file).splitlines()
            if line.strip()
        ]
        scope_paths = legacy
        active_paths = legacy
    return run_gate(parse_labels(args.labels), scope_paths, active_paths=active_paths)


if __name__ == "__main__":
    raise SystemExit(main())