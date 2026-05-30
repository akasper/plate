import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class PrDocumentationGateReleaseNotesTests(unittest.TestCase):
    def test_feature_documentation_gate_requires_release_change_files(self):
        workflow = (REPO_ROOT / ".github" / "workflows" / "pr-documentation-check.yml").read_text(encoding="utf-8")

        self.assertIn(".agentic/releases/", workflow)
        self.assertIn("per-feature change files", workflow)
        self.assertNotIn("CURRENT.md", workflow)


if __name__ == "__main__":
    unittest.main()
