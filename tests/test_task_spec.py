"""Tests for agent crew task spec schema and validator (#1333)."""

from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from plate_core.cli import main
from plate_core.task_spec import (
    TASK_SPEC_VERSION,
    infer_role_from_issue,
    load_task_spec_yaml,
    resolve_effective_tool_allow_list,
    task_spec_schema,
    validate_task_spec_paths,
    validate_task_spec_document,
)

_EXAMPLES = Path("src/plate_core/data/examples")
_RESEARCH = _EXAMPLES / "task-spec-research-synthesis.yml"
_DESIGN = _EXAMPLES / "task-spec-design-from-research.yml"


class TaskSpecSchemaTests(unittest.TestCase):
    def test_schema_file_loads_and_matches_version(self):
        schema = task_spec_schema()
        self.assertEqual(schema["properties"]["task_spec_version"]["const"], TASK_SPEC_VERSION)

    def test_shipped_examples_validate_together(self):
        reports = validate_task_spec_paths([_RESEARCH, _DESIGN])
        self.assertEqual(len(reports), 2)
        for report in reports:
            self.assertTrue(report.valid, report.errors)

    def test_reject_unknown_role(self):
        doc = load_task_spec_yaml(_RESEARCH)
        doc = dict(doc)
        doc["role"] = "not-a-real-agent"
        report = validate_task_spec_document(doc, path="test.yml", known_task_ids=None)
        self.assertFalse(report.valid)
        self.assertTrue(any("baseline_catalog" in e for e in report.errors))

    def test_t3_requires_human_approval_fields(self):
        doc = load_task_spec_yaml(_DESIGN)
        doc = dict(doc)
        doc["model_policy"] = dict(doc["model_policy"])
        del doc["model_policy"]["t3_requires_approval"]
        report = validate_task_spec_document(doc, path="test.yml")
        self.assertFalse(report.valid)

    def test_infer_role_from_issue_kind(self):
        self.assertEqual(infer_role_from_issue("Research", []), "research-agent")
        self.assertEqual(infer_role_from_issue("Bug", []), "software-engineer")

    def test_resolve_effective_tools_merges_profile_and_allow(self):
        doc = load_task_spec_yaml(_RESEARCH)
        tools = resolve_effective_tool_allow_list(doc["tools"])
        self.assertIn("plate_what_next", tools)
        self.assertIn("plate_list_questions", tools)


class TaskSpecCliTests(unittest.TestCase):
    def test_cli_tasks_validate_json(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(
                [
                    "tasks",
                    "validate",
                    "--path",
                    str(_RESEARCH),
                    "--path",
                    str(_DESIGN),
                    "--json",
                ]
            )
        self.assertEqual(code, 0)
        payload = json.loads(out.getvalue())
        self.assertTrue(payload["valid"])

    def test_python_module_entrypoint(self):
        from plate_core.task_spec import main as spec_main

        out = io.StringIO()
        with redirect_stdout(out):
            code = spec_main(["--path", str(_RESEARCH), "--path", str(_DESIGN)])
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
