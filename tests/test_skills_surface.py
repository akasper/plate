import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from plate_core.baseline_catalog import BaselineSkill, load_baseline_catalog
from plate_core.skills_surface import (
    expected_plugin_skill_paths,
    plugin_skills_surfaces_in_sync,
    render_skill_md,
    render_skills_md,
    write_plugin_skills_surfaces,
)


class SkillsSurfaceTests(unittest.TestCase):
    def test_render_skills_md_lists_all_catalog_skills(self):
        catalog = load_baseline_catalog()
        content = render_skills_md()
        self.assertIn("PLATE-GENERATED:BEGIN skills-surface", content)
        self.assertIn("baseline_catalog.yml", content)
        self.assertIn(f"**{len(catalog.skills)}** baseline skills", content)
        for skill in catalog.skills:
            self.assertIn(f"`{skill.id}`", content)
            self.assertIn(skill.name, content)

    def test_render_skill_md_uses_frontmatter_and_catalog_fields(self):
        skill = BaselineSkill(
            id="demo-skill",
            name="Demo Skill",
            description="Demonstrate generated plugin skill payloads.",
            inputs=("Input A",),
            outputs=("Output A",),
            examples=("Do the thing.",),
            owning_agent_ids=("research-agent",),
        )
        content = render_skill_md(skill)
        self.assertIn("name: Demo Skill", content)
        self.assertIn("description: Demonstrate generated plugin skill payloads.", content)
        self.assertIn("Skill id: `demo-skill`", content)
        self.assertIn("- Input A", content)
        self.assertIn("- Output A", content)
        self.assertIn("- Do the thing.", content)

    def test_expected_plugin_skill_paths_cover_both_surfaces(self):
        repo_root = Path(__file__).resolve().parents[1]
        expected = expected_plugin_skill_paths(repo_root)
        catalog = load_baseline_catalog()
        self.assertEqual(len(expected), 2 * (1 + len(catalog.skills)))
        self.assertIn(repo_root / "plugin" / "SKILLS.md", expected)
        self.assertIn(repo_root / ".plugin" / "SKILLS.md", expected)
        for skill in catalog.skills:
            self.assertIn(repo_root / "plugin" / "skills" / skill.id / "SKILL.md", expected)
            self.assertIn(repo_root / ".plugin" / "skills" / skill.id / "SKILL.md", expected)

    def test_write_plugin_skills_surfaces_is_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            (repo_root / "plugin").mkdir()
            (repo_root / ".plugin").mkdir()
            with patch("plate_core.skills_surface.load_baseline_catalog", load_baseline_catalog):
                first = write_plugin_skills_surfaces(repo_root)
                second = write_plugin_skills_surfaces(repo_root)
            self.assertEqual(first.written_paths, second.written_paths)
            ok, errors = plugin_skills_surfaces_in_sync(repo_root)
            self.assertTrue(ok, msg="\n".join(errors))

    def test_plugin_skills_surfaces_in_sync_detects_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            (repo_root / "plugin").mkdir()
            (repo_root / ".plugin").mkdir()
            with patch("plate_core.skills_surface.load_baseline_catalog", load_baseline_catalog):
                write_plugin_skills_surfaces(repo_root)
                skills_md = repo_root / "plugin" / "SKILLS.md"
                skills_md.write_text(skills_md.read_text(encoding="utf-8") + "\n# stale edit\n", encoding="utf-8")
                ok, errors = plugin_skills_surfaces_in_sync(repo_root)
            self.assertFalse(ok)
            self.assertTrue(any("plugin/SKILLS.md" in error for error in errors))

    def test_generate_script_check_passes_in_repo(self):
        import subprocess

        repo_root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            ["python3", str(repo_root / "scripts" / "generate-plugin-skills.py"), "--check"],
            capture_output=True,
            text=True,
            cwd=repo_root,
            env={"PYTHONPATH": str(repo_root / "src"), **dict(__import__("os").environ)},
        )
        self.assertEqual(result.returncode, 0, msg=f"{result.stderr}\n{result.stdout}")
        self.assertIn("Plugin skill surfaces OK", result.stdout)


if __name__ == "__main__":
    unittest.main()
