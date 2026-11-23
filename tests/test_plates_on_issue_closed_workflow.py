"""Regression tests for plates-on-issue-closed workflow (#1472 S3)."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

from plate_core.issue_closed_usage import (
    COST_ROW_MARKER,
    UsageCostRow,
    issue_has_harvest_type_label,
    is_trusted_recorded_cost_row_comment,
    is_trusted_usage_report_author,
    parse_validated_usage_fields,
    resolve_harvest_issue_type,
    select_trusted_usage_report_comment,
    workflow_github_script,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
REPO_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "plates-on-issue-closed.yml"
PAYLOAD_WORKFLOW = (
    REPO_ROOT
    / "src"
    / "plate_core"
    / "template_payload"
    / ".github"
    / "workflows"
    / "plates-on-issue-closed.yml"
)


def _comment(
    body: str,
    *,
    login: str = "akasper",
    association: str = "OWNER",
    url: str = "https://github.com/o/r/issues/1#issuecomment-1",
) -> dict:
    return {
        "body": body,
        "user": {"login": login},
        "author_association": association,
        "html_url": url,
    }


class IssueClosedUsageTrustTests(unittest.TestCase):
    def test_untrusted_author_ignored(self):
        comments = [
            _comment(
                "=== USAGE REPORT ===\ntokens: 10\ncost: $0.01\nduration: 00:01:00\n=== END USAGE REPORT ===",
                login="random-contributor",
                association="NONE",
            ),
            _comment(
                "=== USAGE REPORT ===\ntokens: 20\ncost: $0.02\nduration: 00:02:00\n=== END USAGE REPORT ===",
                login="akasper",
                association="OWNER",
                url="https://github.com/o/r/issues/1#issuecomment-2",
            ),
        ]
        picked = select_trusted_usage_report_comment(comments)
        self.assertIsNotNone(picked)
        self.assertEqual(picked["html_url"], comments[1]["html_url"])

    def test_malformed_fields_rejected(self):
        comments = [
            _comment(
                "=== USAGE REPORT ===\ntokens: not-a-number\ncost: $0.01\nduration: 00:01:00\n=== END USAGE REPORT ===",
            ),
            _comment(
                "=== USAGE REPORT ===\ntokens: 10\ncost: free\nduration: 00:01:00\n=== END USAGE REPORT ===",
            ),
        ]
        self.assertIsNone(select_trusted_usage_report_comment(comments))

    def test_parse_validated_usage_fields_strict(self):
        ok = parse_validated_usage_fields("tokens: 999\ncost: $12.34\nduration: 01:02:03")
        self.assertEqual(ok, {"tokens": "999", "cost": "$12.34", "duration": "01:02:03"})
        self.assertIsNone(parse_validated_usage_fields("tokens: 1\ncost: $1\nduration: 1:2:3"))

    def test_explicit_bot_allowlist(self):
        self.assertTrue(
            is_trusted_usage_report_author(
                author_association="NONE", login="github-actions[bot]"
            )
        )
        self.assertFalse(
            is_trusted_usage_report_author(author_association="NONE", login="evil-bot")
        )

    def test_forged_cost_row_marker_ignored_for_already_recorded(self):
        source = "https://github.com/o/r/issues/1#issuecomment-2"
        forged = _comment(
            f"{COST_ROW_MARKER}\n{source}",
            login="evil-user",
            association="NONE",
        )
        trusted = _comment(
            f"{COST_ROW_MARKER}\n{source}",
            login="github-actions[bot]",
            association="NONE",
        )
        self.assertFalse(
            is_trusted_recorded_cost_row_comment(forged, source_comment_url=source)
        )
        self.assertTrue(
            is_trusted_recorded_cost_row_comment(trusted, source_comment_url=source)
        )


class IssueClosedUsageLabelAndRowTests(unittest.TestCase):
    def test_exact_label_matching(self):
        self.assertFalse(
            issue_has_harvest_type_label([{"name": "Documentation"}, {"name": "Featurefoo"}])
        )
        self.assertTrue(issue_has_harvest_type_label([{"name": "Question"}]))
        self.assertEqual(
            resolve_harvest_issue_type([{"name": "Feature"}, {"name": "area:security"}]),
            "Feature",
        )

    def test_markdown_row_uses_issue_link_only(self):
        row = UsageCostRow(
            closed_at_iso="2026-11-15T00:00:00.000Z",
            issue_number=1472,
            issue_html_url="https://github.com/akasper/plate/issues/1472",
            issue_type="Bug",
            tokens="100",
            cost="$0.10",
            duration="00:05:00",
            source_comment_url="https://github.com/akasper/plate/issues/1472#issuecomment-9",
        )
        line = row.markdown_table_row()
        self.assertIn("[#1472](https://github.com/akasper/plate/issues/1472)", line)
        self.assertNotIn("Untrusted issue title", line)


class PlatesOnIssueClosedWorkflowCodegenTests(unittest.TestCase):
    def test_build_script_writes_matching_embedded_script(self):
        spec = importlib.util.spec_from_file_location(
            "build_plates_on_issue_closed_workflow",
            REPO_ROOT / "scripts" / "build_plates_on_issue_closed_workflow.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        self.assertEqual(
            mod.build(github_script_version="v8"),
            REPO_WORKFLOW.read_text(encoding="utf-8"),
        )
        self.assertEqual(
            mod.build(github_script_version="v7"),
            PAYLOAD_WORKFLOW.read_text(encoding="utf-8"),
        )
        text = REPO_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("contains(format(',{0},'", text)
        self.assertNotIn(
            "join(github.event.issue.labels.*.name, ','), 'Feature'",
            text,
            "label gate must use delimiter-padded match, not substring join",
        )
        self.assertIn(
            "github.event.issue.number",
            text,
            "per-issue concurrency group avoids dropped harvests",
        )

    def test_workflow_github_script_guards(self):
        script = workflow_github_script()
        self.assertIn("const issueCell = ", script)
        self.assertIn("issue.html_url", script)
        self.assertNotIn("issue.title", script)
        self.assertIn("isRecordedCostRow", script)
        self.assertIn("github-actions[bot]", script)


if __name__ == "__main__":
    unittest.main()