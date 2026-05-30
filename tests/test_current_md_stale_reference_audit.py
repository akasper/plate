import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def read(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


class CurrentMdStaleReferenceAuditTests(unittest.TestCase):
    def test_core_process_and_templates_no_longer_require_current_md(self):
        process = read(".agentic/process.yml")
        pr_template = read(".github/PULL_REQUEST_TEMPLATE.md")
        issue_template = read(".github/ISSUE_TEMPLATE/feature.yml")
        labels = read(".github/labels.yml")
        codeowners = read(".github/CODEOWNERS")

        self.assertNotIn('current_state: "CURRENT.md"', process)
        self.assertNotIn("feature_pr_requires_current_md: true", process)
        self.assertNotIn("CURRENT.md", pr_template)
        self.assertNotIn("CURRENT.md", issue_template)
        self.assertNotIn("CURRENT.md", labels)
        self.assertNotIn("/CURRENT.md", codeowners)

    def test_sync_wiki_workflow_no_longer_copies_current_md(self):
        workflow = read(".github/workflows/sync-wiki-on-merge.yml")
        self.assertNotIn("cp CURRENT.md", workflow)
        self.assertIn(".agentic/releases/", workflow)

    def test_current_md_is_deprecation_stub(self):
        current = read("CURRENT.md")
        self.assertIn("Deprecated", current)
        self.assertIn(".agentic/releases/", current)


if __name__ == "__main__":
    unittest.main()
