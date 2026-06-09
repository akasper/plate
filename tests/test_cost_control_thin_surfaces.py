import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class ThinSurfaceContractTests(unittest.TestCase):
    def test_plate_agent_prompt_is_routing_oriented_and_under_budget(self):
        path = REPO_ROOT / "plugin" / "agents" / "plate.agent.md"
        content = path.read_text(encoding="utf-8")

        self.assertLess(path.stat().st_size, 4500)
        self.assertIn("plate_what_next", content)
        self.assertIn("plate_delegate_to_agent", content)
        self.assertIn("gh plate context list/show", content)
        self.assertIn("AGENTS.md", content)
        self.assertIn("SPEC.md", content)
        self.assertIn("gh plate release status", content)

    def test_repo_copilot_instructions_have_quick_routing_and_under_budget(self):
        path = REPO_ROOT / ".github" / "copilot-instructions.md"
        content = path.read_text(encoding="utf-8")

        self.assertLess(path.stat().st_size, 6000)
        self.assertIn("## Quick routing", content)
        self.assertIn("gh plate context list/show", content)
        self.assertIn("AGENTS.md", content)
        self.assertIn("SPEC.md", content)
        self.assertIn(".agentic/releases/", content)
        self.assertIn("gh plate release status", content)
        self.assertIn("gh plate agents list/show", content)

    def test_template_copilot_instructions_have_quick_routing_and_under_budget(self):
        path = REPO_ROOT / "src" / "plate_core" / "template_payload" / ".github" / "copilot-instructions.md"
        content = path.read_text(encoding="utf-8")

        self.assertLess(path.stat().st_size, 11000)
        self.assertIn("## Quick routing", content)
        self.assertIn("gh plate context list/show", content)
        self.assertIn("AGENTS.md", content)
        self.assertIn(".agentic/releases/", content)
        self.assertIn("gh plate release status", content)
        self.assertIn("docs/bootstrap/new-repository-checklist.md", content)
        self.assertIn("scripts/validate_plate_repo.sh .", content)


if __name__ == "__main__":
    unittest.main()
