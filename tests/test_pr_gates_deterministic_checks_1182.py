"""Deterministic PR gate checks for pytest policy and release fragments (#1182)."""

from __future__ import annotations

import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from plate_core.pr_gates_checks import (
    check_feature_release_fragment,
    is_pure_docs_chore_exempt,
)
from plate_core.pr_gates_test_policy import (
    find_pytest_violations_in_source,
    scan_test_paths,
)
from plate_core.pr_release_fragment_gate import run_gate as run_fragment_gate
from plate_core.pr_unittest_policy_gate import run_gate as run_unittest_gate

REPO_ROOT = Path(__file__).resolve().parents[1]


class UnittestPolicyGateTests(unittest.TestCase):
    def test_datetime_import_is_not_a_pytest_violation(self):
        source = "from datetime import datetime, timezone\nimport unittest\n"
        self.assertEqual(find_pytest_violations_in_source(source), [])

    def test_pytest_import_is_a_violation(self):
        source = "import pytest\n"
        violations = find_pytest_violations_in_source(source, path="tests/test_new.py")
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0].path, "tests/test_new.py")

    def test_pytest_in_string_literal_is_ignored(self):
        source = 'self.assertIn("targeted pytest", text)\n'
        self.assertEqual(find_pytest_violations_in_source(source), [])

    def test_gate_fails_on_changed_test_with_pytest(self):
        paths = ["tests/test_new.py", "src/foo.py"]

        def reader(_path: str) -> str:
            return "import pytest\n"

        with patch.object(sys, "stderr", new_callable=io.StringIO) as err:
            code = run_unittest_gate(paths, read_text=reader)
        self.assertEqual(code, 1)
        self.assertIn("stdlib unittest policy", err.getvalue())

    def test_gate_passes_on_clean_changed_test(self):
        paths = ["tests/test_new.py"]

        def reader(_path: str) -> str:
            return "import unittest\n\nclass T(unittest.TestCase):\n    pass\n"

        self.assertEqual(run_unittest_gate(paths, read_text=reader), 0)


class ReleaseFragmentExemptTests(unittest.TestCase):
    def test_pure_docs_chore_exempt_accepts_docs_markdown_only(self):
        self.assertTrue(
            is_pure_docs_chore_exempt(["docs/design/note.md", "README.md"])
        )

    def test_process_path_blocks_exemption(self):
        self.assertFalse(
            is_pure_docs_chore_exempt(["docs/note.md", "src/plate_core/foo.py"])
        )

    def test_feature_without_fragment_fails_on_code_change(self):
        failure = check_feature_release_fragment(
            ["Feature"], ["src/plate_core/cli.py"]
        )
        self.assertIsNotNone(failure)

    def test_feature_without_fragment_passes_for_docs_chore(self):
        self.assertIsNone(
            check_feature_release_fragment(
                ["Feature"], ["docs/research/1182-note.md"]
            )
        )

    def test_fragment_gate_cli_fails_and_passes(self):
        with patch.object(sys, "stderr", new_callable=io.StringIO):
            fail_code = run_fragment_gate(
                ["Feature"], ["src/plate_core/x.py"]
            )
        self.assertEqual(fail_code, 1)
        self.assertEqual(
            run_fragment_gate(
                ["Feature"],
                [".agentic/releases/unreleased/slug.json"],
            ),
            0,
        )
        self.assertEqual(
            run_fragment_gate(["Feature"], ["docs/wiki/Home.md"]),
            0,
        )


if __name__ == "__main__":
    unittest.main()