"""CLI interface used by gh-plate extension entrypoint."""

from __future__ import annotations

import argparse
import json

from .epics import get_epic_status
from .features import get_features
from .health import get_health


def cmd_health(args: argparse.Namespace) -> int:
    report = get_health(args.repo)
    if args.json:
        print(json.dumps(report.to_dict()))
        return 0

    print(f"Repo: {report.repo}")
    print(f"Status: {report.status.upper()}")
    print(f"Label coverage: {'OK' if report.label_coverage_ok else 'MISSING'}")
    if report.missing_labels:
        print(f"Missing labels: {', '.join(report.missing_labels)}")
    print(f"Branch protection: {'ENABLED' if report.branch_protection_enabled else 'DISABLED'}")
    print(f"Open Epics: {report.open_epic_count}")
    return 0 if report.status != "fail" else 1


def cmd_epic_status(args: argparse.Namespace) -> int:
    report = get_epic_status(args.repo)
    if args.json:
        print(json.dumps(report.to_dict()))
        return 0

    print(f"Repo: {report.repo}")
    print(f"Open Epics: {report.open_epic_count}")
    if not report.epics:
        print("No Epic:* labels found.")
        return 0
    for epic in report.epics:
        print(f"- {epic.epic_label}")
        if epic.epic_issue_number is not None:
            print(
                f"  Epic issue: #{epic.epic_issue_number} ({(epic.epic_issue_state or 'unknown').upper()})"
                f" {epic.epic_issue_title or ''}".rstrip()
            )
        print(f"  Children: open={epic.open_child_issues}, closed={epic.closed_child_issues}")
    return 0


def cmd_features(args: argparse.Namespace) -> int:
    report = get_features(args.repo)
    if args.json:
        print(json.dumps(report.to_dict()))
        return 0

    print(f"Repo: {report.repo}")
    for feature in report.features:
        print(f"- {feature.name}: {'ENABLED' if feature.enabled else 'DISABLED'} ({feature.evidence})")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gh plate", description="PLATE core CLI extension")
    sub = parser.add_subparsers(dest="command", required=True)

    health = sub.add_parser("health", help="Show PLATE health summary")
    health.add_argument("--repo", help="owner/name; defaults to git remote origin")
    health.add_argument("--json", action="store_true", help="Output JSON")
    health.set_defaults(func=cmd_health)

    epic = sub.add_parser("epic", help="Epic-related PLATE commands")
    epic_sub = epic.add_subparsers(dest="epic_command", required=True)
    status = epic_sub.add_parser("status", help="Show Epic status summary")
    status.add_argument("--repo", help="owner/name; defaults to git remote origin")
    status.add_argument("--json", action="store_true", help="Output JSON")
    status.set_defaults(func=cmd_epic_status)

    features = sub.add_parser("features", help="Show optional PLATE feature detection")
    features.add_argument("--repo", help="owner/name; defaults to git remote origin")
    features.add_argument("--json", action="store_true", help="Output JSON")
    features.set_defaults(func=cmd_features)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)
