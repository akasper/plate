"""plate-pr-gates payload helpers — shared failure lines for CI (#1418)."""

from __future__ import annotations

import argparse
import json
import sys

from .pr_gates_checks import (
    closing_keyword_fix_message,
    issue_link_gate_failure_lines,
    suggest_issue_number_for_closing_fix,
)


def _cmd_closing_fix_line(args: argparse.Namespace) -> int:
    body = args.body
    if args.body_file:
        body = open(args.body_file, encoding="utf-8").read()
    if body is None:
        body = sys.stdin.read()
    labels = [part.strip() for part in (args.labels or "").split(",") if part.strip()]
    lines = issue_link_gate_failure_lines(
        body,
        labels,
        owner=args.owner,
        repo=args.repo,
        has_sidebar_link=False,
    )
    if lines:
        print(lines[0])
        return 0
    issue_num = suggest_issue_number_for_closing_fix(body)
    print(closing_keyword_fix_message(issue_number=issue_num))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PLATE plate-pr-gates payload helpers")
    sub = parser.add_subparsers(dest="command", required=True)

    fix = sub.add_parser(
        "closing-fix-line",
        help="Print the exact closing-keyword fix line for a PR body",
    )
    fix.add_argument("--body", help="PR body text")
    fix.add_argument("--body-file", help="Read PR body from file")
    fix.add_argument(
        "--labels",
        default="",
        help="Comma-separated PR labels (for exemption checks)",
    )
    fix.add_argument("--owner", help="GitHub owner for URL-scoped closing keywords")
    fix.add_argument("--repo", help="GitHub repo name for URL-scoped closing keywords")
    fix.set_defaults(func=_cmd_closing_fix_line)

    parsed = parser.parse_args(argv)
    return int(parsed.func(parsed))


if __name__ == "__main__":
    raise SystemExit(main())
