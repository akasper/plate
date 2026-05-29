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
        self.assertIn("must be assigned to a GitHub milestone", workflow)
        self.assertNotIn("must carry exactly one Epic: short-name label", workflow)

    def test_pr_issue_link_check_accepts_development_links(self):
        workflow = read_text(".github/workflows/pr-issue-link-check.yml")

        self.assertIn("CONNECTED_EVENT", workflow)
        self.assertIn("timelineItems", workflow)
        self.assertIn("Development sidebar", workflow)
        self.assertIn("['Feature', 'Bug', 'Documentation']", workflow)

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


if __name__ == "__main__":
    unittest.main()
