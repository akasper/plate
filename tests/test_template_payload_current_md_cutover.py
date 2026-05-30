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


if __name__ == "__main__":
    unittest.main()
