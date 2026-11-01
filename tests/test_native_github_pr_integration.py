import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def read_text(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


class NativeGitHubPrIntegrationTests(unittest.TestCase):
    def test_feature_issue_template_uses_epic_milestones(self):
        template = read_text(".github/ISSUE_TEMPLATE/feature.yml")

        self.assertIn("Epic milestone", template)
        self.assertIn("assigned to the correct epic milestone", template)
        self.assertNotIn("Epic traceability label", template)

    def test_issue_label_check_requires_milestones_not_epic_labels(self):
        workflow = read_text(".github/workflows/label-check.yml")

        self.assertIn("requiresMilestone", workflow)
        self.assertIn("'Release'", workflow)
        self.assertIn("Release issues must be assigned to a GitHub milestone.", workflow)
        self.assertIn("must be assigned to a GitHub milestone", workflow)
        self.assertNotIn("must carry exactly one Epic: short-name label", workflow)
        # Release ceremony refinement: Release issues now also require a milestone
        self.assertIn("'Release'", workflow)  # or the array now includes Release in requiresMilestone

    def test_issue_label_check_accepts_spike_and_allowed_status_labels(self):
        """#1262 items 1–2: Spike type + AGENTS.md status:* exceptions."""
        repo_workflow = read_text(".github/workflows/label-check.yml")
        payload_workflow = read_text(
            "src/plate_core/template_payload/.github/workflows/label-check.yml"
        )
        self.assertEqual(repo_workflow, payload_workflow)
        for workflow in (repo_workflow, payload_workflow):
            self.assertIn("'Spike'", workflow)
            self.assertIn("allowedStatusLabels", workflow)
            self.assertIn("'status:stub'", workflow)
            self.assertIn("'status:blocked'", workflow)
            self.assertIn("'status:ready-to-work'", workflow)
            self.assertIn("'status:implemented'", workflow)
            self.assertNotIn(
                "labels.filter((label) => /^status:|^priority:/.test(label))",
                workflow.replace(" ", ""),
            )

    def test_auto_merge_requires_marker_and_risk_low(self):
        """#1262 item 7: auto-merge stays on AUTONOMOUS_MODE + risk:low only."""
        repo_workflow = read_text(".github/workflows/auto-merge.yml")
        payload_workflow = read_text(
            "src/plate_core/template_payload/.github/workflows/auto-merge.yml"
        )
        self.assertEqual(repo_workflow, payload_workflow)
        for workflow in (repo_workflow, payload_workflow):
            self.assertIn(".github/AUTONOMOUS_MODE", workflow)
            self.assertIn("'risk:low'", workflow)
            self.assertNotIn("risk_tolerance", workflow)

    def test_bootstrap_exits_when_label_sync_failed(self):
        """#1262 item 8: bootstrap must fail when label sync errors occur."""
        for rel in (
            "scripts/bootstrap_github.sh",
            "src/plate_core/template_payload/scripts/bootstrap_github.sh",
        ):
            script = read_text(rel)
            self.assertIn("LABEL_SYNC_FAILED", script)
            self.assertIn('if [[ "$LABEL_SYNC_FAILED" -gt 0 ]]; then', script)
            self.assertIn("exit 1", script)

    def test_payload_agents_merge_gate_documents_pr_gates(self):
        """#1262: payload AGENTS.md references plate-pr-gates, not legacy feedback-resolution."""
        agents = read_text("src/plate_core/template_payload/AGENTS.md")
        self.assertIn("plate-pr-gates.yml", agents)
        self.assertIn("pr-gates", agents)
        self.assertNotIn("feedback-resolution-check.yml", agents)

    def test_conversation_graph_child_pr_closes_child_not_epic(self):
        """#1262 item 9: child PR template closes the child issue."""
        doc = read_text(
            "src/plate_core/template_payload/docs/design/conversation-to-issue-graph.md"
        )
        self.assertIn("Closes #{child_issue_number}", doc)
        self.assertIn("Child PR template", doc)
        self.assertNotIn("copy this keyword into the implementing PR body, where GitHub will then automatically close the issue when the PR merges to the default branch. **OR**", doc)
        self.assertNotIn("Closes #{epic_number}` (preferred)", doc)

    def test_pr_issue_link_check_accepts_development_links(self):
        workflow = read_text(".github/workflows/plate-pr-gates.yml")

        self.assertIn("CONNECTED_EVENT", workflow)
        self.assertIn("timelineItems", workflow)
        self.assertIn("Development sidebar", workflow)
        self.assertIn("['Feature', 'Bug', 'Documentation']", workflow)
        self.assertIn("Warning-only rollout", workflow)
        self.assertIn("gh pr edit", workflow)

    def test_process_and_design_docs_record_warning_first_milestones(self):
        process = read_text(".agentic/process.yml")
        design_doc = read_text("docs/design/native-github-pr-integration.md")

        self.assertIn("required_for_release", process)
        self.assertIn("milestone_enforcement_status: \"warning_first\"", process)
        self.assertIn("Release issues also require milestones", design_doc)
        self.assertIn("warning-first check", design_doc)

    def test_pr_title_check_enforces_human_readable_titles(self):
        workflow = read_text(".github/workflows/plate-pr-gates.yml")

        self.assertIn("hasBracketPrefix", workflow)
        self.assertIn("hasClosingKeyword", workflow)
        self.assertIn("PR titles must be human-readable summaries only.", workflow)
        self.assertIn("closing keywords from the title", workflow)

    def test_bootstrap_scripts_default_branch_deletion_can_be_skipped(self):
        bash_script = read_text("scripts/bootstrap_github.sh")
        powershell_script = read_text("scripts/BootstrapGitHub.ps1")

        self.assertIn("--skip-delete-branch-on-merge", bash_script)
        self.assertIn("SKIP_DELETE_BRANCH_ON_MERGE=false", bash_script)
        self.assertIn("-SkipDeleteBranchOnMerge", powershell_script)
        self.assertIn("$SkipDeleteBranchOnMerge", powershell_script)

    def test_design_artifact_records_native_github_decisions(self):
        design_doc = read_text("docs/design/native-github-pr-integration.md")

        self.assertIn("Milestones are the canonical Epic container", design_doc)
        self.assertIn("Development sidebar links", design_doc)
        self.assertIn("Delete branch on merge", design_doc)

    def test_release_ci_validates_versions_and_remote_tag_conflicts(self):
        workflow = read_text(".github/workflows/plate-pr-gates.yml")

        self.assertIn("Gate — validate release PR", workflow)
        self.assertIn("validate_release_workspace", workflow)
        self.assertIn("git ls-remote --tags origin", workflow)
        self.assertIn("Release tag ${RELEASE_TAG} already exists on origin.", workflow)

    def test_release_workflow_tags_merged_release_pr_commit(self):
        workflow = read_text(".github/workflows/release.yml")

        self.assertIn("pull_request:", workflow)
        self.assertIn("types: [closed]", workflow)
        self.assertIn("github.event.pull_request.merge_commit_sha", workflow)
        self.assertIn('git tag "${RELEASE_TAG}" "${MERGE_SHA}"', workflow)
        self.assertIn('git push origin "refs/tags/${RELEASE_TAG}"', workflow)


if __name__ == "__main__":
    unittest.main()
