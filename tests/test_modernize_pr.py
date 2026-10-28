import unittest

from plate_core.modernize_pr import (
    VERDICT_CLOSE,
    VERDICT_MODERNIZE,
    VERDICT_REWORK,
    git_push_force_with_lease_argv,
    git_range_diff_argv,
    parse_verdict_line,
)


class ModernizePrHelperTests(unittest.TestCase):
    def test_parse_verdict_line(self):
        self.assertEqual(parse_verdict_line("Verdict: MODERNIZE"), VERDICT_MODERNIZE)
        self.assertEqual(parse_verdict_line("  verdict: rework  "), VERDICT_REWORK)
        self.assertEqual(parse_verdict_line("CLOSE"), VERDICT_CLOSE)
        self.assertIsNone(parse_verdict_line("maybe later"))
        self.assertIsNone(parse_verdict_line(""))

    def test_parse_verdict_line_rejects_ambiguous_or_incomplete_1251(self):
        """Regression: only standalone token or exact Verdict: <single-token> (#1251)."""
        self.assertIsNone(parse_verdict_line("Verdict: REWORK, not MODERNIZE"))
        self.assertIsNone(parse_verdict_line("Verdict:"))
        self.assertIsNone(parse_verdict_line("Verdict: "))
        self.assertIsNone(parse_verdict_line("MODERNIZE with extra words"))

    def test_git_range_diff_argv(self):
        argv = git_range_diff_argv(
            base="origin/main",
            pre_rebase_head="abc1234",
            post_rebase_head="def5678",
        )
        self.assertEqual(
            argv,
            [
                "git",
                "range-diff",
                "origin/main..abc1234",
                "origin/main..def5678",
            ],
        )

    def test_git_range_diff_argv_uses_two_dot_pr_series_1251(self):
        """Regression: two-dot ranges compare PR commits only, not merge-base triple-dot (#1251)."""
        argv = git_range_diff_argv(
            base="origin/release",
            pre_rebase_head="aaa",
            post_rebase_head="bbb",
        )
        self.assertTrue(all(".." in arg and "..." not in arg for arg in argv[2:]))

    def test_git_range_diff_argv_requires_refs(self):
        with self.assertRaises(ValueError):
            git_range_diff_argv(base="", pre_rebase_head="a", post_rebase_head="b")

    def test_git_push_force_with_lease_argv(self):
        argv = git_push_force_with_lease_argv(
            remote="origin",
            branch="feature/foo",
            pre_rebase_head="deadbeef",
        )
        self.assertEqual(
            argv,
            [
                "git",
                "push",
                "origin",
                "HEAD:refs/heads/feature/foo",
                "--force-with-lease=refs/heads/feature/foo:deadbeef",
            ],
        )

    def test_git_push_force_with_lease_uses_head_refspec_detached_worktree_1251(self):
        """Regression: push HEAD to branch ref in detached worktree (#1251)."""
        argv = git_push_force_with_lease_argv(
            remote="origin",
            branch="feature/foo",
            pre_rebase_head="deadbeef",
        )
        self.assertEqual(argv[3], "HEAD:refs/heads/feature/foo")

    def test_git_push_force_with_lease_argv_requires_refs(self):
        with self.assertRaises(ValueError):
            git_push_force_with_lease_argv(remote="origin", branch="", pre_rebase_head="x")


class ModernizePrSkillArtifactTests(unittest.TestCase):
    def test_modernize_pr_skill_ships_in_all_surfaces_1235(self):
        from pathlib import Path

        skill_path = Path("plugin/skills/modernize-pr/SKILL.md")
        self.assertTrue(skill_path.is_file(), "modernize-pr skill must ship under plugin/skills/")
        skill = skill_path.read_text(encoding="utf-8")
        self.assertIn("never close and never merge", skill.lower())
        self.assertIn("force-with-lease", skill)
        self.assertIn("range-diff", skill)
        self.assertIn("MODERNIZE", skill)
        self.assertIn("REWORK", skill)
        self.assertIn("CLOSE", skill)
        self.assertIn("isolated", skill.lower())

        self.assertTrue(
            Path(".plugin/skills/modernize-pr/SKILL.md").is_file(),
            "skill must be mirrored under .plugin/skills/",
        )
        template_skill = Path(
            "src/plate_core/template_payload/.agentic/skills/modernize-pr/SKILL.md"
        )
        self.assertTrue(
            template_skill.is_file(),
            "modernize-pr skill must ship in template payload for bootstrap",
        )

        with open("AGENTS.md", encoding="utf-8") as f:
            agents = f.read()
        self.assertIn("modernize-pr-skill-1235", agents)
        self.assertIn("modernize-pr", agents)


if __name__ == "__main__":
    unittest.main()
