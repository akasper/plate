import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from plate_core.agents_surface import (
    plugin_agents_surfaces_in_sync,
    render_agent_md,
    render_agents_md,
    write_plugin_agents_surfaces,
)
from plate_core.baseline_catalog import BaselineAgent, load_baseline_catalog


class AgentsSurfaceTests(unittest.TestCase):
    def test_render_agents_md_lists_all_catalog_agents(self):
        catalog = load_baseline_catalog()
        content = render_agents_md()
        self.assertIn("PLATE-GENERATED:BEGIN agents-surface", content)
        self.assertIn("baseline_catalog.yml", content)
        self.assertIn(f"**{len(catalog.agents)}** narrow baseline roles", content)
        for agent in catalog.agents:
            self.assertIn(f"`{agent.id}`", content)
            self.assertIn(agent.name, content)

    def test_render_agent_md_includes_profiles_and_skills(self):
        agent = BaselineAgent(
            id="demo-agent",
            name="Demo Agent",
            description="Demonstrate generated plugin agent payloads.",
            primary_skill_ids=("demo-skill",),
            constraints=("Stay scoped.",),
            surfaces=("copilot-plugin",),
            default_tool_profiles=("default", "design"),
        )
        content = render_agent_md(agent)
        self.assertIn("name: demo-agent", content)
        self.assertIn("Default MCP tool profiles", content)
        self.assertIn("`demo-skill`", content)
        self.assertIn("`design`", content)

    def test_write_plugin_agents_surfaces_is_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            (repo_root / "plugin" / "agents").mkdir(parents=True)
            (repo_root / ".plugin" / "agents").mkdir(parents=True)
            manual = repo_root / "plugin" / "agents" / "plate.agent.md"
            manual.write_text("# plate\n", encoding="utf-8")
            with patch("plate_core.agents_surface.load_baseline_catalog", load_baseline_catalog):
                first = write_plugin_agents_surfaces(repo_root)
                second = write_plugin_agents_surfaces(repo_root)
            self.assertEqual(first.written_paths, second.written_paths)
            self.assertTrue(manual.read_text(encoding="utf-8").startswith("# plate"))
            ok, errors = plugin_agents_surfaces_in_sync(repo_root)
            self.assertTrue(ok, msg="\n".join(errors))

    def test_generate_script_check_passes_in_repo(self):
        import subprocess

        repo_root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            ["python3", str(repo_root / "scripts" / "generate-plugin-agents.py"), "--check"],
            capture_output=True,
            text=True,
            cwd=repo_root,
            env={"PYTHONPATH": str(repo_root / "src"), **dict(__import__("os").environ)},
        )
        self.assertEqual(result.returncode, 0, msg=f"{result.stderr}\n{result.stdout}")


if __name__ == "__main__":
    unittest.main()
