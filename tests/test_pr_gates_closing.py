"""Regression tests for strict PR closing-keyword parsing (#1231)."""

from __future__ import annotations

import unittest

from plate_core.pr_gates_closing import (
    body_has_strict_closing_keyword,
    parse_strict_closing_issue_numbers,
    strip_closing_scan_text,
)
from plate_core.pr_gates_contract import (
    validate_closing_keyword_parsing_contract,
    validate_feature_fragment_ignores_removed_files,
    validate_sidebar_link_replay_contract,
    workflow_paths,
)


class TestStrictClosingKeywords(unittest.TestCase):
    def test_fixes_three_race_conditions_does_not_match(self):
        body = "This PR fixes 3 race conditions in the gate runner."
        self.assertFalse(body_has_strict_closing_keyword(body))
        self.assertEqual(parse_strict_closing_issue_numbers(body), [])

    def test_explicit_hash_reference_matches(self):
        body = "Summary\n\nFixes #1231\n"
        self.assertTrue(body_has_strict_closing_keyword(body))
        self.assertEqual(parse_strict_closing_issue_numbers(body), [1231])

    def test_issue_url_matches(self):
        body = "Closes https://github.com/akasper/plate/issues/99"
        self.assertEqual(parse_strict_closing_issue_numbers(body), [99])

    def test_fenced_code_ignored(self):
        body = "Real link: Closes #10\n\n```md\nCloses #999\n```\n"
        self.assertEqual(parse_strict_closing_issue_numbers(body), [10])

    def test_html_comment_ignored(self):
        body = "Closes #11\n<!-- Closes #888 -->\n"
        self.assertEqual(parse_strict_closing_issue_numbers(body), [11])

    def test_strip_closing_scan_text(self):
        raw = "a<!-- hide Closes #1 -->b\n```js\nCloses #2\n```\nCloses #3"
        stripped = strip_closing_scan_text(raw)
        self.assertNotIn("#1", stripped)
        self.assertNotIn("#2", stripped)
        self.assertIn("#3", stripped)


class TestWorkflowContracts1231(unittest.TestCase):
    def test_committed_workflows_satisfy_1231_contracts(self):
        repo_path, payload_path = workflow_paths()
        for path in (repo_path, payload_path):
            text = path.read_text(encoding="utf-8")
            for validator in (
                validate_closing_keyword_parsing_contract,
                validate_sidebar_link_replay_contract,
                validate_feature_fragment_ignores_removed_files,
            ):
                errors = validator(text)
                self.assertEqual(errors, [], msg=f"{path}: {errors}")


if __name__ == "__main__":
    unittest.main()
