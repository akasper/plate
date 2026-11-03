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
    LEVEL_TIER_POLICY,
    infer_role_from_issue,
    issue_risk_requires_human_approver,
    level_tier_policy_table,
    load_task_spec_yaml,
    recommended_start_tier,
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
        policy = schema["$defs"]["level_to_tier_policy"]["default"]
        self.assertEqual(len(policy), 3)
        self.assertEqual(policy[0]["level"], "junior")
        self.assertEqual(policy[0]["default_tier"], "T1")

    def test_level_tier_policy_table_matches_schema(self):
        table = level_tier_policy_table()
        schema_rows = task_spec_schema()["$defs"]["level_to_tier_policy"]["default"]
        self.assertEqual(len(table), len(schema_rows))
        for row, schema_row in zip(table, schema_rows, strict=True):
            self.assertEqual(row["level"], schema_row["level"])
            self.assertEqual(row["default_tier"], schema_row["default_tier"])
            self.assertEqual(row["allowed_tiers"], schema_row["allowed_tiers"])
            self.assertEqual(row["human_assignable"], schema_row["human_assignable"])
        self.assertEqual(len(LEVEL_TIER_POLICY), 3)

    def test_recommended_start_tier_junior_docs_uses_cheapest_when_ci(self):
        self.assertEqual(
            recommended_start_tier(
                "junior",
                "docs",
                allowed_tiers=["T1", "T2"],
                ci_validates_output=True,
            ),
            "T1",
        )
        self.assertEqual(
            recommended_start_tier(
                "junior",
                "tests",
                allowed_tiers=["T0", "T1"],
                ci_validates_output=True,
            ),
            "T0",
        )
        self.assertEqual(
            recommended_start_tier("junior", "docs", allowed_tiers=["T0", "T1"]),
            "T1",
        )
        self.assertEqual(
            recommended_start_tier("senior", "docs", allowed_tiers=["T1", "T2"]),
            "T2",
        )

    def test_reject_senior_start_below_mapped_initial(self):
        doc = load_task_spec_yaml(_RESEARCH)
        doc = dict(doc)
        doc["model_policy"] = {
            "tiers": ["T1", "T2"],
            "start_tier": "T1",
            "max_cost_usd": 0.5,
        }
        report = validate_task_spec_document(doc, path="test.yml")
        self.assertFalse(report.valid)
        self.assertTrue(any("mapped initial tier" in e for e in report.errors))

    def test_reject_staff_start_below_mapped_initial(self):
        doc = load_task_spec_yaml(_DESIGN)
        doc = dict(doc)
        doc["model_policy"] = dict(doc["model_policy"])
        doc["model_policy"]["start_tier"] = "T2"
        report = validate_task_spec_document(doc, path="test.yml")
        self.assertFalse(report.valid)
        self.assertTrue(any("mapped initial tier" in e for e in report.errors))

    def test_issue_risk_critical_requires_human_gate(self):
        self.assertTrue(issue_risk_requires_human_approver(["risk:critical"]))
        self.assertFalse(issue_risk_requires_human_approver(["risk:high"]))

    def test_reject_tier_outside_level_band(self):
        doc = load_task_spec_yaml(_RESEARCH)
        doc = dict(doc)
        doc["model_policy"] = {
            "tiers": ["T0"],
            "start_tier": "T0",
            "max_cost_usd": 0.5,
        }
        doc["approval"] = "none"
        report = validate_task_spec_document(doc, path="test.yml")
        self.assertFalse(report.valid)
        self.assertTrue(any("not allowed for level" in e for e in report.errors))

    def test_reject_junior_docs_start_above_cheapest_when_ci(self):
        doc = load_task_spec_yaml(_RESEARCH)
        doc = dict(doc)
        doc["level"] = "junior"
        doc["route"] = "docs"
        doc["acceptance"] = dict(doc["acceptance"])
        doc["acceptance"]["ci_validates_output"] = True
        doc["model_policy"] = {
            "tiers": ["T0", "T1"],
            "start_tier": "T1",
            "max_cost_usd": 0.5,
        }
        doc["approval"] = "none"
        report = validate_task_spec_document(doc, path="test.yml")
        self.assertFalse(report.valid)
        self.assertTrue(any("ci_validates_output" in e for e in report.errors))

    def test_junior_docs_without_ci_allows_default_start(self):
        doc = load_task_spec_yaml(_RESEARCH)
        doc = dict(doc)
        doc["level"] = "junior"
        doc["route"] = "docs"
        doc["model_policy"] = {
            "tiers": ["T0", "T1"],
            "start_tier": "T1",
            "max_cost_usd": 0.5,
        }
        doc["approval"] = "none"
        report = validate_task_spec_document(doc, path="test.yml")
        self.assertTrue(report.valid, report.errors)

    def test_risk_critical_requires_human_approval_in_spec(self):
        doc = load_task_spec_yaml(_RESEARCH)
        doc = dict(doc)
        doc["approval"] = "none"
        report = validate_task_spec_document(
            doc,
            path="test.yml",
            issue_labels=["risk:critical"],
        )
        self.assertFalse(report.valid)
        self.assertTrue(any("risk:critical" in e for e in report.errors))

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
        self.assertEqual(
            infer_role_from_issue("Feature", ["area:product"]),
            "product-manager",
        )
        self.assertEqual(
            infer_role_from_issue("Epic", ["area:agent"]),
            "team-lead",
        )
        self.assertEqual(
            infer_role_from_issue("Feature", ["area:marketing"]),
            "marketing-specialist",
        )

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
