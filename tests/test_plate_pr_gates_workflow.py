import unittest
from pathlib import Path

from plate_core.pr_gates_contract import (
    PLATE_PR_GATES_CHECK_NAME,
    PR_GATE_STEP_CONTRACTS,
    find_stale_required_check_contexts,
    missing_recommended_check_contexts,
    validate_merged_pr_gates_workflow,
    workflow_paths,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


class PlatePrGatesWorkflowTests(unittest.TestCase):
    def test_repo_and_payload_workflows_share_gate_steps(self):
        repo_path, payload_path = workflow_paths(REPO_ROOT)
        repo_text = repo_path.read_text(encoding="utf-8")
        payload_text = payload_path.read_text(encoding="utf-8")
        for gate in PR_GATE_STEP_CONTRACTS:
            name = gate["step_name"]
            self.assertIn(name, repo_text, f"repo missing {name}")
            self.assertIn(name, payload_text, f"payload missing {name}")
            marker = gate.get("failure_marker") or ""
            if marker:
                self.assertIn(marker, repo_text)
                self.assertIn(marker, payload_text)

    def test_contract_validation_passes_on_committed_workflows(self):
        repo_path, _ = workflow_paths(REPO_ROOT)
        errors = validate_merged_pr_gates_workflow(repo_path.read_text(encoding="utf-8"))
        self.assertEqual(errors, [])

    def test_each_gate_failure_message_is_distinct(self):
        markers = [
            g["failure_marker"]
            for g in PR_GATE_STEP_CONTRACTS
            if g.get("failure_marker")
        ]
        self.assertEqual(len(markers), len(set(markers)))

    def test_stale_branch_protection_detection(self):
        stale = find_stale_required_check_contexts(
            ["labels", "test", "check-pr-title", "pr-gates"]
        )
        self.assertEqual(stale, ["check-pr-title"])

    def test_recommended_check_name_is_pr_gates(self):
        self.assertEqual(PLATE_PR_GATES_CHECK_NAME, "pr-gates")

    def test_recommended_checks_match_branch_protection_case_insensitively(self):
        self.assertEqual(
            missing_recommended_check_contexts(["Labels", "test", "pr-gates"]),
            [],
        )


if __name__ == "__main__":
    unittest.main()
