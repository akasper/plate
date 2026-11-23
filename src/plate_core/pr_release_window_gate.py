"""PR gate: block release-integration bases while Next Release window is open (#1439)."""

from __future__ import annotations

import argparse
import sys

from plate_core.pr_gates_checks import RELEASE_WINDOW_FAILURE_HEADING, check_release_window
from plate_core.release import get_release_status


def parse_labels(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


def run_gate(*, base: str, labels: list[str], repo: str | None) -> int:
    status = get_release_status(repo)
    failure = check_release_window(
        base,
        labels,
        release_window_open=bool(status.release_window_open),
    )
    if failure is None:
        return 0
    print(
        "\n".join(
            [
                f"## ⚠️ {RELEASE_WINDOW_FAILURE_HEADING}",
                "",
                failure.message,
            ]
        ),
        file=sys.stderr,
    )
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PLATE release-window PR gate (#1439)")
    parser.add_argument("--base", required=True, help="PR base ref")
    parser.add_argument(
        "--labels",
        default="",
        help="Comma-separated PR labels",
    )
    parser.add_argument(
        "--repo",
        default=None,
        help="owner/name (default: gh repo resolution)",
    )
    args = parser.parse_args(argv)
    return run_gate(base=args.base, labels=parse_labels(args.labels), repo=args.repo)


if __name__ == "__main__":
    raise SystemExit(main())
