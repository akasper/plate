"""PR gate: only release branches may merge to main (#1435)."""

from __future__ import annotations

import argparse
import sys

from plate_core.pr_gates_checks import (
    MAIN_SOURCE_FAILURE_HEADING,
    check_main_source,
)


def parse_labels(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


def run_gate(*, base: str, head: str, labels: list[str]) -> int:
    failure = check_main_source(base, head, labels)
    if failure is None:
        return 0
    print(
        "\n".join(
            [
                f"## ⚠️ {MAIN_SOURCE_FAILURE_HEADING}",
                "",
                failure.message,
            ]
        ),
        file=sys.stderr,
    )
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PLATE main-source PR gate (#1435)")
    parser.add_argument("--base", required=True, help="PR base ref")
    parser.add_argument("--head", required=True, help="PR head ref")
    parser.add_argument(
        "--labels",
        default="",
        help="Comma-separated PR labels",
    )
    args = parser.parse_args(argv)
    return run_gate(base=args.base, head=args.head, labels=parse_labels(args.labels))


if __name__ == "__main__":
    raise SystemExit(main())
