import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_ROOT = REPO_ROOT / "src" / "plate_core" / "template_payload"


def read(relative_path: str) -> str:
    return (TEMPLATE_ROOT / relative_path).read_text(encoding="utf-8")


class TemplatePayloadCurrentMdCutoverTests(unittest.TestCase):
    def test_template_payload_no_longer_ships_current_md(self):
        self.assertFalse((TEMPLATE_ROOT / "CURRENT.md").exists())

    def test_template_agents_and_readme_reference_release_change_files(self):
        agents = read("AGENTS.md")
        readme = read("README.md")

        self.assertIn(".agentic/releases/", agents)
        self.assertIn(".agentic/releases/", readme)
        self.assertNotIn("CURRENT.md", agents)
        self.assertNotIn("CURRENT.md", readme)

    def test_template_feature_gate_uses_release_change_files(self):
        workflow = read(".github/workflows/pr-documentation-check.yml")
        self.assertIn(".agentic/releases/", workflow)
        self.assertNotIn("CURRENT.md", workflow)

    def test_template_payload_includes_release_issue_template(self):
        release_template = TEMPLATE_ROOT / ".github" / "ISSUE_TEMPLATE" / "release.yml"
        self.assertTrue(release_template.exists())
        content = release_template.read_text(encoding="utf-8")
        self.assertIn('title: "Next Release"', content)
        self.assertIn("pre_release_checklist", content)
        self.assertIn("release-artifact and remote tag-conflict checks", content)
        self.assertIn("merged Release PR commit", content)

    def test_template_process_tracks_refined_release_ceremony(self):
        process = read(".agentic/process.yml")
        self.assertIn("release_notes:", process)
        self.assertIn("milestones_are_canonical_epics: true", process)
        self.assertIn("Standing 'Next Release' issue exists", process)
        self.assertIn(".agentic/releases/unreleased/", process)

    def test_template_payload_workflows_use_milestones_and_fragments(self):
        label_check = read(".github/workflows/label-check.yml")
        issue_link = read(".github/workflows/pr-issue-link-check.yml")
        doc_check = read(".github/workflows/pr-documentation-check.yml")
        ci = read(".github/workflows/ci.yml")
        release = read(".github/workflows/release.yml")

        self.assertIn("requiresMilestone", label_check)
        self.assertIn("Release issues must be assigned to a GitHub milestone.", label_check)
        self.assertIn("Development sidebar", issue_link)
        self.assertIn("--milestone", issue_link)
        self.assertIn(".agentic/releases/unreleased/", doc_check)
        self.assertIn("release fragment", doc_check)
        self.assertIn("validate-release-pr", ci)
        self.assertIn("git ls-remote --tags origin", ci)
        self.assertIn("pull_request:", release)
        self.assertIn("github.event.pull_request.merge_commit_sha", release)


if __name__ == "__main__":
    unittest.main()
