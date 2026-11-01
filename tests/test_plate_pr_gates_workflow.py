import unittest
from pathlib import Path

from plate_core.pr_gates_contract import (
    PLATE_PR_GATES_CHECK_NAME,
    PR_GATE_STEP_CONTRACTS,
    find_stale_required_check_contexts,
    missing_recommended_check_contexts,
    validate_feature_fragment_gate_on_all_admitted_pr_events,
    validate_merged_pr_gates_workflow,
    validate_pr_gates_multi_label_event_safety,
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
        repo_path, payload_path = workflow_paths(REPO_ROOT)
        for path in (repo_path, payload_path):
            errors = validate_merged_pr_gates_workflow(path.read_text(encoding="utf-8"))
            self.assertEqual(errors, [], msg=f"{path}: {errors}")

    def test_multi_label_event_safety_on_committed_workflows(self):
        repo_path, payload_path = workflow_paths(REPO_ROOT)
        for path in (repo_path, payload_path):
            errors = validate_pr_gates_multi_label_event_safety(
                path.read_text(encoding="utf-8")
            )
            self.assertEqual(errors, [], msg=f"{path}: {errors}")

    def test_feature_fragment_gate_on_area_or_risk_label_events(self):
        """area:* / risk:* labels admit pr-gates; fragment step must still run (#1239)."""
        stale_if = """
      - name: Gate — Feature release fragment
        if: |
          github.event_name == 'pull_request' && steps.feature_labels.outputs.is_feature == 'true' && (
            contains(fromJSON('["opened","synchronize","reopened","edited"]'), github.event.action) ||
            (github.event.action == 'labeled' && github.event.label.name == 'Feature')
          )
        uses: actions/github-script@v8
          script: |
            core.setFailed('per-feature change files');
"""
        errors = validate_feature_fragment_gate_on_all_admitted_pr_events(stale_if)
        self.assertEqual(len(errors), 1)
        self.assertIn("area:*", errors[0])

        repo_path, payload_path = workflow_paths(REPO_ROOT)
        for path in (repo_path, payload_path):
            errors = validate_feature_fragment_gate_on_all_admitted_pr_events(
                path.read_text(encoding="utf-8")
            )
            self.assertEqual(errors, [], msg=f"{path}: {errors}")

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

    def test_pr_gates_does_not_run_unused_runs_on_probe(self):
        repo_path, payload_path = workflow_paths(REPO_ROOT)
        for path in (repo_path, payload_path):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn(
                "Select runs-on for heavy jobs",
                text,
                msg=f"{path}: pr-gates should not probe runners without using output",
            )

    def test_review_event_safety_on_committed_workflows(self):
        from plate_core.pr_gates_contract import validate_pr_gates_review_event_safety

        repo_path, payload_path = workflow_paths(REPO_ROOT)
        for path in (repo_path, payload_path):
            errors = validate_pr_gates_review_event_safety(
                path.read_text(encoding="utf-8")
            )
            self.assertEqual(errors, [], msg=f"{path}: {errors}")

    def test_review_event_if_requires_both_event_equalities(self):
        from plate_core.pr_gates_contract import (
            _step_if_requires_both_review_events,
        )

        comment_only = """
      - name: Gate — PR title
        if: |
          github.event_name == 'pull_request_review_comment'
        uses: actions/github-script@v8
"""
        comment_only_if = comment_only.split("uses:")[0]
        self.assertEqual(
            _step_if_requires_both_review_events(comment_only_if),
            ["missing exact github.event_name == 'pull_request_review' comparison"],
        )
        review_only = """
      - name: Gate — issue links
        if: |
          github.event_name == 'pull_request_review'
        uses: actions/github-script@v8
"""
        self.assertIn(
            "pull_request_review_comment",
            _step_if_requires_both_review_events(review_only.split("uses:")[0])[0],
        )

    def test_build_plate_pr_gates_workflow_regenerates_without_diff(self):
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "build_plate_pr_gates_workflow",
            REPO_ROOT / "scripts" / "build_plate_pr_gates_workflow.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        repo_path, payload_path = workflow_paths(REPO_ROOT)
        self.assertEqual(
            mod.build("plate"),
            repo_path.read_text(encoding="utf-8"),
        )
        self.assertEqual(
            mod.build("template"),
            payload_path.read_text(encoding="utf-8"),
        )

    def test_local_composite_action_requires_checkout_first(self):
        """Local ./.github/actions/* must run after actions/checkout (#1222)."""
        workflow_paths_to_check = [
            REPO_ROOT / ".github" / "workflows" / "ci.yml",
            REPO_ROOT
            / "src"
            / "plate_core"
            / "template_payload"
            / ".github"
            / "workflows"
            / "ci.yml",
            REPO_ROOT
            / "src"
            / "plate_core"
            / "template_payload"
            / ".github"
            / "workflows"
            / "test-e2e.yml",
        ]
        for path in workflow_paths_to_check:
            text = path.read_text(encoding="utf-8")
            if "./.github/actions/plate-select-runs-on" not in text:
                continue
            action_idx = text.index("./.github/actions/plate-select-runs-on")
            checkout_idx = text.index("actions/checkout")
            self.assertLess(
                checkout_idx,
                action_idx,
                f"{path}: actions/checkout must appear before plate-select-runs-on",
            )

    def test_recommended_checks_match_branch_protection_case_insensitively(self):
        self.assertEqual(
            missing_recommended_check_contexts(["Labels", "test", "pr-gates"]),
            [],
        )


if __name__ == "__main__":
    unittest.main()
