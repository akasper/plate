"""Deterministic PR gate checks for pytest policy and release fragments (#1182)."""

from __future__ import annotations

import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from plate_core.pr_gate_paths import parse_scope_tsv
from plate_core.pr_gates_checks import (
    check_feature_release_fragment,
    is_pure_docs_chore_exempt,
)
from plate_core.pr_gates_test_policy import find_pytest_violations_in_source, scan_test_paths
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

    def test_grouped_pytest_import_is_a_violation(self):
        source = "import unittest, pytest as pt\n"
        violations = find_pytest_violations_in_source(source)
        self.assertEqual(len(violations), 1)

    def test_pytest_mark_decorator_is_a_violation(self):
        source = "@pytest.mark.slow\nclass T(unittest.TestCase):\n    pass\n"
        violations = find_pytest_violations_in_source(source)
        self.assertGreaterEqual(len(violations), 1)

    def test_from_pytest_import_is_a_violation(self):
        source = "from pytest import raises\n"
        self.assertEqual(len(find_pytest_violations_in_source(source)), 1)

    def test_importlib_pytest_is_a_violation(self):
        source = "import importlib\nimportlib.import_module('pytest')\n"
        self.assertEqual(len(find_pytest_violations_in_source(source)), 1)

    def test_pytest_in_triple_quoted_string_is_ignored(self):
        source = (
            'class T(unittest.TestCase):\n'
            '    def test_doc(self):\n'
            '        sample = """\n'
            'import pytest\n'
            '"""\n'
            '        self.assertIn("import", sample)\n'
        )
        self.assertEqual(find_pytest_violations_in_source(source), [])

    def test_pytest_in_string_literal_is_ignored(self):
        source = 'self.assertIn("targeted pytest", text)\n'
        self.assertEqual(find_pytest_violations_in_source(source), [])

    def test_conftest_pytest_import_is_a_violation(self):
        source = "import pytest\n"
        violations = find_pytest_violations_in_source(source, path="tests/conftest.py")
        self.assertEqual(len(violations), 1)

    def test_unparseable_file_is_a_violation(self):
        source = "def oops(\n"
        violations = find_pytest_violations_in_source(source)
        self.assertEqual(len(violations), 1)
        self.assertIn("unparseable", violations[0].line)

    def test_gate_fails_on_changed_test_with_pytest(self):
        paths = ["tests/test_new.py"]

        def reader(_path: str) -> str:
            return "import pytest\n"

        with patch.object(sys, "stderr", new_callable=io.StringIO) as err:
            code = run_unittest_gate(paths, read_text=reader)
        self.assertEqual(code, 1)
        self.assertIn("stdlib unittest policy", err.getvalue())

    def test_gate_fails_closed_on_unreadable_file(self):
        paths = ["tests/test_new.py"]

        def reader(_path: str) -> str:
            raise OSError("missing")

        self.assertEqual(run_unittest_gate(paths, read_text=reader), 1)

    def test_gate_passes_on_clean_changed_test(self):
        paths = ["tests/test_new.py"]

        def reader(_path: str) -> str:
            return "import unittest\n\nclass T(unittest.TestCase):\n    pass\n"

        self.assertEqual(run_unittest_gate(paths, read_text=reader), 0)


class ReleaseFragmentExemptTests(unittest.TestCase):
    def test_pure_docs_chore_exempt_accepts_docs_markdown_only(self):
        self.assertTrue(is_pure_docs_chore_exempt(["docs/design/note.md"]))

    def test_readme_at_root_is_not_exempt(self):
        self.assertFalse(is_pure_docs_chore_exempt(["README.md"]))

    def test_config_path_blocks_exemption(self):
        self.assertFalse(is_pure_docs_chore_exempt(["docs/note.md", ".github/workflows/ci.yml"]))

    def test_removed_code_blocks_exemption(self):
        scope = parse_scope_tsv("src/plate_core/foo.py\tremoved\ndocs/chore.md\tmodified")
        paths = [entry.path for entry in scope]
        self.assertFalse(is_pure_docs_chore_exempt(paths))

    def test_process_path_blocks_exemption(self):
        self.assertFalse(
            is_pure_docs_chore_exempt(["docs/note.md", "src/plate_core/foo.py"])
        )

    def test_feature_without_fragment_fails_on_code_change(self):
        failure = check_feature_release_fragment(
            ["Feature"], ["src/plate_core/cli.py"], active_paths=["src/plate_core/cli.py"]
        )
        self.assertIsNotNone(failure)

    def test_feature_without_fragment_passes_for_docs_chore(self):
        self.assertIsNone(
            check_feature_release_fragment(
                ["Feature"],
                ["docs/research/1182-note.md"],
                active_paths=["docs/research/1182-note.md"],
            )
        )

    def test_fragment_gate_cli_fails_and_passes(self):
        with patch.object(sys, "stderr", new_callable=io.StringIO):
            fail_code = run_fragment_gate(
                ["Feature"],
                ["src/plate_core/x.py"],
                active_paths=["src/plate_core/x.py"],
            )
        self.assertEqual(fail_code, 1)
        self.assertEqual(
            run_fragment_gate(
                ["Feature"],
                [".agentic/releases/unreleased/slug.json"],
                active_paths=[".agentic/releases/unreleased/slug.json"],
            ),
            0,
        )
        self.assertEqual(
            run_fragment_gate(
                ["Feature"],
                ["docs/research/home.md"],
                active_paths=["docs/research/home.md"],
            ),
            0,
        )

    def test_feature_and_hardening_labels_fail_fragment_gate(self):
        with patch.object(sys, "stderr", new_callable=io.StringIO) as err:
            code = run_fragment_gate(
                ["Feature", "Hardening"],
                ["src/plate_core/x.py"],
                active_paths=["src/plate_core/x.py"],
            )
        self.assertEqual(code, 1)
        self.assertIn("exactly one type label", err.getvalue())


if __name__ == "__main__":
    unittest.main()