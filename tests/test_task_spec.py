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
    TaskRunSnapshot,
    infer_role_from_issue,
    issue_risk_requires_human_approver,
    level_tier_policy_table,
    load_task_spec_yaml,
    next_run_state,
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

    def _minimal_doc(self, **model_policy: object) -> dict:
        base = load_task_spec_yaml(_RESEARCH)
        doc = dict(base)
        doc["model_policy"] = {
            "tiers": ["T1", "T2"],
            "start_tier": "T2",
            "max_cost_usd": 0.5,
            **model_policy,
        }
        return doc

    def test_reject_multi_step_escalation(self):
        for from_tier, to_tier in (("T0", "T2"), ("T1", "T3"), ("T0", "T3")):
            with self.subTest(from_tier=from_tier, to_tier=to_tier):
                doc = self._minimal_doc(
                    tiers=[from_tier, to_tier],
                    start_tier=from_tier,
                    escalation={"from": from_tier, "to": to_tier},
                )
                if from_tier == "T1":
                    doc["model_policy"]["tiers"] = ["T1", "T2", "T3"]
                report = validate_task_spec_document(doc, path="test.yml")
                self.assertFalse(report.valid)
                self.assertTrue(
                    any("exactly one tier step" in e for e in report.errors),
                    report.errors,
                )

    def test_reject_escalation_from_not_equal_start_tier(self):
        doc = self._minimal_doc(
            start_tier="T2",
            escalation={"from": "T1", "to": "T2"},
        )
        report = validate_task_spec_document(doc, path="test.yml")
        self.assertFalse(report.valid)
        self.assertTrue(
            any("escalation.from must equal" in e for e in report.errors),
            report.errors,
        )

    def test_valid_one_step_escalation(self):
        doc = self._minimal_doc(
            start_tier="T2",
            tiers=["T2", "T3"],
            escalation={"from": "T2", "to": "T3"},
            t3_requires_approval="human",
        )
        doc["approval"] = "human-t3"
        report = validate_task_spec_document(doc, path="test.yml")
        self.assertTrue(report.valid, report.errors)

    def test_next_run_state_table(self):
        spec_escalate_t2 = {
            "model_policy": {
                "escalation": {"from": "T1", "to": "T2"},
            }
        }
        spec_escalate_t3 = {
            "model_policy": {
                "escalation": {"from": "T2", "to": "T3"},
            }
        }
        spec_no_escalation: dict = {"model_policy": {}}
        cases = [
            ("start", True, spec_escalate_t2, "done"),
            ("escalated", True, spec_escalate_t2, "done"),
            ("start", False, spec_escalate_t2, "escalated"),
            ("start", False, spec_escalate_t3, "awaiting_human"),
            ("start", False, spec_no_escalation, "stopped_reported"),
            ("escalated", False, spec_escalate_t2, "stopped_reported"),
            ("awaiting_human", False, spec_escalate_t3, "stopped_reported"),
            ("awaiting_human", True, spec_escalate_t3, "done"),
        ]
        for state, outcome_ok, spec, expected in cases:
            with self.subTest(state=state, outcome_ok=outcome_ok, expected=expected):
                got = next_run_state(TaskRunSnapshot(state=state), outcome_ok, spec)
                self.assertEqual(got, expected)

    def test_t3_escalation_requires_awaiting_human(self):
        spec = {"model_policy": {"escalation": {"from": "T2", "to": "T3"}}}
        self.assertEqual(
            next_run_state("start", False, spec),
            "awaiting_human",
        )

    def test_second_failure_after_escalation_stops(self):
        spec = {"model_policy": {"escalation": {"from": "T1", "to": "T2"}}}
        self.assertEqual(
            next_run_state("escalated", False, spec),
            "stopped_reported",
        )


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
