import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def read(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


class CurrentMdReferenceDocsTests(unittest.TestCase):
    def test_agents_guidance_uses_release_note_change_files(self):
        agents = read("AGENTS.md")
        self.assertIn("per-feature change files", agents)
        self.assertNotIn("Every Feature pull request must modify `CURRENT.md`.", agents)
        self.assertNotIn("| 5 | Update `CURRENT.md`", agents)

    def test_contributing_removes_feature_current_requirement(self):
        contributing = read("CONTRIBUTING.md")
        self.assertNotIn("Feature PRs must update `CURRENT.md`.", contributing)
        self.assertIn(".agentic/releases/", contributing)

    def test_readme_points_sync_flow_at_release_notes(self):
        readme = read("README.md")
        self.assertNotIn("CURRENT.md", readme)
        self.assertIn(".agentic/releases/", readme)

    def test_wiki_home_points_to_release_notes(self):
        wiki_home = read("docs/wiki/Home.md")
        self.assertNotIn("Link to `CURRENT.md`", wiki_home)
        self.assertIn(".agentic/releases/", wiki_home)

    def test_copilot_instructions_replace_current_sync_rule(self):
        instructions = read(".github/copilot-instructions.md")
        self.assertNotIn("Keep `CURRENT.md` and release-note files in sync", instructions)
        self.assertIn("per-feature change files", instructions)


if __name__ == "__main__":
    unittest.main()
