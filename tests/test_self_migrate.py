"""Tests for self-migrate dry-run plan and marker merge (#939/#943 / Epic #649)."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from plate_core.self_migrate import (
    apply_self_migrate_pr,
    plan_marker_merge,
    plan_self_migrate,
    plan_self_migrate_pr,
    resolve_upstream_version,
    verify_self_migrate,
)
from plate_core.cli import cmd_self_migrate


class PlanSelfMigrateTests(unittest.TestCase):
    def test_no_pin_no_drift_with_matching_target(self):
        """Proves: empty pin + default target uses installed version (#939)."""
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "AGENTS.md").write_text("# local\n", encoding="utf-8")
            report = plan_self_migrate(root, target_version="0.7.2")
        self.assertTrue(report["ok"])
        self.assertEqual(report["target_version"], "0.7.2")
        self.assertFalse(report["auto_apply"])
        self.assertEqual(report["mode"], "dry_run_plan")
        self.assertTrue(report["steps"])
        paths = {p["path"] for p in report["refresh_paths_present"]}
        self.assertIn("AGENTS.md", paths)

    def test_pin_behind_target_marks_drift(self):
        """Proves: VERSION pin behind target sets drift and upgrade step (#939)."""
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "VERSION").write_text("0.6.0\n", encoding="utf-8")
            (root / "AGENTS.md").write_text(
                "<!-- PLATES-CORE:BEGIN demo -->\nx\n<!-- PLATES-CORE:END demo -->\n",
                encoding="utf-8",
            )
            report = plan_self_migrate(root, target_version="0.7.2")
        self.assertTrue(report["drift"])
        self.assertEqual(report["pin"]["version"], "0.6.0")
        self.assertEqual(report["comparisons"]["pin_vs_target"], "behind")
        step_ids = [s["id"] for s in report["steps"]]
        self.assertIn("2_upgrade_runtime", step_ids)
        self.assertIn("4_import_payload", step_ids)
        markers = [
            p for p in report["refresh_paths_present"] if p["path"] == "AGENTS.md"
        ]
        self.assertTrue(markers[0]["has_plates_core_markers"])

    def test_pyproject_plate_core_pin(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pyproject.toml").write_text(
                '[project]\ndependencies = ["plate-core==0.5.1"]\n',
                encoding="utf-8",
            )
            report = plan_self_migrate(root, target_version="0.7.2")
        self.assertEqual(report["pin"]["version"], "0.5.1")
        self.assertEqual(report["pin"]["source"], "pyproject.toml")
        self.assertTrue(report["drift"])

    def test_no_payload_omits_import_step(self):
        with TemporaryDirectory() as tmp:
            report = plan_self_migrate(tmp, target_version="0.7.2", include_payload=False)
        ids = [s["id"] for s in report["steps"]]
        self.assertNotIn("4_import_payload", ids)

    def test_cmd_self_migrate_json(self):
        with TemporaryDirectory() as tmp:
            (Path(tmp) / "VERSION").write_text("0.7.2\n", encoding="utf-8")
            ns = type(
                "NS",
                (),
                {
                    "repo_root": tmp,
                    "target_version": "0.7.2",
                    "no_payload": False,
                    "plan": True,
                    "json": True,
                    "merge_markers": False,
                    "apply_markers": False,
                    "upstream_dir": None,
                    "path": None,
                    "resolve_upstream": False,
                    "allow_network": False,
                    "pr_plan": False,
                    "apply_pr": False,
                    "allow_high_risk": False,
                    "base": "release",
                    "closes": None,
                },
            )()
            import io
            import sys

            buf = io.StringIO()
            old = sys.stdout
            try:
                sys.stdout = buf
                rc = cmd_self_migrate(ns)
            finally:
                sys.stdout = old
            self.assertEqual(rc, 0)
            data = json.loads(buf.getvalue())
            self.assertTrue(data["ok"])
            self.assertIn("steps", data)


_LOCAL_AGENTS = """# Local title

Local intro outside markers.

<!-- PLATES-CORE:BEGIN demo -->
old core block
<!-- PLATES-CORE:END demo -->

Local footer stays.
"""

_UPSTREAM_AGENTS = """# Upstream title (should not replace outside)

Upstream intro.

<!-- PLATES-CORE:BEGIN demo -->
new core block from upstream
<!-- PLATES-CORE:END demo -->

Upstream footer.
"""


class ResolveUpstreamVersionTests(unittest.TestCase):
    def test_offline_default_no_version(self):
        """Proves: offline resolve returns no version and does not error (#945)."""
        report = resolve_upstream_version(allow_network=False)
        self.assertTrue(report["ok"])
        self.assertIsNone(report["version"])
        self.assertEqual(report["source"], "offline_default")
        self.assertFalse(report["used_network"])

    def test_injected_fetcher_pypi_json(self):
        """Proves: injected fetcher sets version from PyPI JSON shape (#945)."""
        payload = {"info": {"version": "0.9.1"}, "releases": {"0.9.1": []}}

        def fetcher():
            return payload

        report = resolve_upstream_version(fetcher=fetcher)
        self.assertTrue(report["ok"])
        self.assertEqual(report["version"], "0.9.1")
        self.assertEqual(report["source"], "injected_fetcher")
        self.assertFalse(report["used_network"])

    def test_injected_fetcher_plain_text(self):
        report = resolve_upstream_version(fetcher=lambda: "v1.2.3\n")
        self.assertEqual(report["version"], "1.2.3")

    def test_fetcher_error_returns_ok_false(self):
        def boom():
            raise TimeoutError("timeout")

        report = resolve_upstream_version(fetcher=boom)
        self.assertFalse(report["ok"])
        self.assertIsNone(report["version"])
        self.assertIn("timeout", report["error"] or "")

    def test_plan_uses_resolved_target_for_drift(self):
        """Proves: resolve_upstream with fetcher marks pin behind newer target (#945)."""
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "VERSION").write_text("0.7.2\n", encoding="utf-8")
            report = plan_self_migrate(
                root,
                resolve_upstream=True,
                upstream_fetcher=lambda: {"info": {"version": "0.9.0"}},
                include_payload=False,
            )
        self.assertEqual(report["target_version"], "0.9.0")
        self.assertTrue(report["drift"])
        self.assertEqual(report["comparisons"]["pin_vs_target"], "behind")
        self.assertIsNotNone(report.get("upstream"))
        self.assertEqual(report["upstream"]["version"], "0.9.0")

    def test_explicit_target_wins_over_resolve(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = plan_self_migrate(
                root,
                target_version="0.8.0",
                resolve_upstream=True,
                upstream_fetcher=lambda: {"info": {"version": "0.9.0"}},
                include_payload=False,
            )
        self.assertEqual(report["target_version"], "0.8.0")


class PlanSelfMigratePrTests(unittest.TestCase):
    def test_no_drift_not_eligible(self):
        """Proves: matching pin/target yields no PR eligibility (#947)."""
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "VERSION").write_text("0.7.2\n", encoding="utf-8")
            report = plan_self_migrate_pr(
                root, target_version="0.7.2", include_payload=False
            )
        self.assertTrue(report["ok"])
        self.assertFalse(report.get("eligible"))
        self.assertEqual(report.get("reason"), "no_drift")

    def test_pin_equals_target_not_drift_when_installed_ahead(self):
        """Proves: pin==explicit target is no-drift even if installed is newer (#984).

        Packaging cuts bump plate_core.__version__ while tests and adopters may
        still pin an older explicit target; installed-ahead must not false-positive.
        """
        from plate_core import __version__ as installed

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "VERSION").write_text("0.7.2\n", encoding="utf-8")
            report = plan_self_migrate(
                root, target_version="0.7.2", include_payload=False
            )
        self.assertEqual(report["comparisons"]["pin_vs_target"], "equal")
        # After 0.8.0 cut the monorepo installed version is ahead of 0.7.2.
        if installed != "0.7.2":
            self.assertEqual(report["comparisons"]["installed_vs_target"], "ahead")
        self.assertFalse(report["drift"])

    def test_pin_behind_eligible_low_risk(self):
        """Proves: VERSION pin behind target is low-risk eligible PR plan (#947)."""
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "VERSION").write_text("0.6.0\n", encoding="utf-8")
            report = plan_self_migrate_pr(
                root,
                target_version="0.7.2",
                include_payload=False,
                closes="#947",
            )
        self.assertTrue(report["ok"])
        self.assertTrue(report["eligible"])
        self.assertEqual(report["risk"], "low")
        self.assertFalse(report["high_risk"])
        self.assertEqual(report["base"], "release")
        self.assertIn("0.7.2", report["title"])
        self.assertIn("Closes #947", report["body"])
        self.assertIn("gh", report["gh_argv"][0])
        self.assertIn("VERSION", report["paths"][0] if report["paths"] else "")

    def test_apply_dry_run_default(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "VERSION").write_text("0.6.0\n", encoding="utf-8")
            plan = plan_self_migrate_pr(root, target_version="0.7.2", include_payload=False)
            applied = apply_self_migrate_pr(plan, dry_run=True)
        self.assertTrue(applied["ok"])
        self.assertTrue(applied["dry_run"])
        self.assertFalse(applied["applied"])
        self.assertTrue(applied["would_execute"])

    def test_apply_live_without_runner_blocked(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "VERSION").write_text("0.6.0\n", encoding="utf-8")
            plan = plan_self_migrate_pr(root, target_version="0.7.2", include_payload=False)
            applied = apply_self_migrate_pr(plan, dry_run=False, runner=None)
        self.assertFalse(applied["ok"])
        self.assertEqual(applied["error"], "runner_required")

    def test_apply_live_with_runner(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "VERSION").write_text("0.6.0\n", encoding="utf-8")
            plan = plan_self_migrate_pr(root, target_version="0.7.2", include_payload=False)

            def runner(p):
                return {"pr_url": "https://example.test/pr/1", "branch": p["branch"]}

            applied = apply_self_migrate_pr(plan, dry_run=False, runner=runner)
        self.assertTrue(applied["ok"])
        self.assertTrue(applied["applied"])
        self.assertEqual(applied["runner_result"]["pr_url"], "https://example.test/pr/1")

    def test_cmd_pr_plan_json(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "VERSION").write_text("0.6.0\n", encoding="utf-8")
            ns = type(
                "NS",
                (),
                {
                    "repo_root": str(root),
                    "target_version": "0.7.2",
                    "no_payload": True,
                    "plan": False,
                    "json": True,
                    "merge_markers": False,
                    "apply_markers": False,
                    "upstream_dir": None,
                    "path": None,
                    "resolve_upstream": False,
                    "allow_network": False,
                    "pr_plan": True,
                    "apply_pr": False,
                    "allow_high_risk": False,
                    "base": "release",
                    "closes": "#947",
                },
            )()
            import io
            import sys

            buf = io.StringIO()
            old = sys.stdout
            try:
                sys.stdout = buf
                rc = cmd_self_migrate(ns)
            finally:
                sys.stdout = old
            self.assertEqual(rc, 0)
            data = json.loads(buf.getvalue())
            self.assertTrue(data["ok"])
            self.assertTrue(data["eligible"])


class PlanMarkerMergeTests(unittest.TestCase):
    def test_dry_run_updates_marker_preserves_outside(self):
        """Proves: dry-run plans marker update without writing; outside local kept (#943)."""
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "AGENTS.md").write_text(_LOCAL_AGENTS, encoding="utf-8")
            report = plan_marker_merge(
                root,
                paths=["AGENTS.md"],
                upstream_texts={"AGENTS.md": _UPSTREAM_AGENTS},
                apply=False,
            )
        self.assertTrue(report["ok"])
        self.assertEqual(report["mode"], "dry_run")
        self.assertEqual(report["would_write"], 1)
        self.assertEqual(report["written"], 0)
        f0 = report["files"][0]
        self.assertEqual(f0["action"], "update_markers")
        self.assertTrue(f0["changed"])
        # File on disk unchanged
        with TemporaryDirectory() as tmp2:
            root = Path(tmp2)
            agents = root / "AGENTS.md"
            agents.write_text(_LOCAL_AGENTS, encoding="utf-8")
            plan_marker_merge(
                root,
                paths=["AGENTS.md"],
                upstream_texts={"AGENTS.md": _UPSTREAM_AGENTS},
                apply=False,
            )
            self.assertEqual(agents.read_text(encoding="utf-8"), _LOCAL_AGENTS)

    def test_apply_writes_markers_keeps_local_outside(self):
        """Proves: apply writes upstream marker body and keeps local outside text (#943)."""
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            agents = root / "AGENTS.md"
            agents.write_text(_LOCAL_AGENTS, encoding="utf-8")
            report = plan_marker_merge(
                root,
                paths=["AGENTS.md"],
                upstream_texts={"AGENTS.md": _UPSTREAM_AGENTS},
                apply=True,
            )
            text = agents.read_text(encoding="utf-8")
        self.assertTrue(report["ok"])
        self.assertEqual(report["written"], 1)
        self.assertIn("new core block from upstream", text)
        self.assertIn("Local intro outside markers.", text)
        self.assertIn("Local footer stays.", text)
        self.assertNotIn("Upstream intro.", text)
        self.assertNotIn("old core block", text)

    def test_local_edit_preserved_when_base_differs(self):
        """Proves: local marker customization wins when base is old upstream (#943)."""
        base = """<!-- PLATES-CORE:BEGIN demo -->
old core block
<!-- PLATES-CORE:END demo -->
"""
        local = """header local

<!-- PLATES-CORE:BEGIN demo -->
user customized core
<!-- PLATES-CORE:END demo -->

footer local
"""
        upstream = """<!-- PLATES-CORE:BEGIN demo -->
new core block from upstream
<!-- PLATES-CORE:END demo -->
"""
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "AGENTS.md").write_text(local, encoding="utf-8")
            report = plan_marker_merge(
                root,
                paths=["AGENTS.md"],
                upstream_texts={"AGENTS.md": upstream},
                base_texts={"AGENTS.md": base},
                apply=True,
            )
            text = (root / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("user customized core", text)
        self.assertNotIn("new core block from upstream", text)
        self.assertIn("demo", report["files"][0]["preserved_local_sections"])

    def test_missing_upstream_reports_skip(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "AGENTS.md").write_text(_LOCAL_AGENTS, encoding="utf-8")
            report = plan_marker_merge(root, paths=["AGENTS.md"], apply=False)
        self.assertEqual(report["files"][0]["action"], "missing_upstream")
        self.assertEqual(report["would_write"], 0)

    def test_cmd_merge_markers_json(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "AGENTS.md").write_text(_LOCAL_AGENTS, encoding="utf-8")
            up = root / "upstream"
            up.mkdir()
            (up / "AGENTS.md").write_text(_UPSTREAM_AGENTS, encoding="utf-8")
            ns = type(
                "NS",
                (),
                {
                    "repo_root": str(root),
                    "target_version": None,
                    "no_payload": False,
                    "plan": False,
                    "json": True,
                    "merge_markers": True,
                    "apply_markers": False,
                    "upstream_dir": str(up),
                    "path": ["AGENTS.md"],
                    "verify": False,
                },
            )()
            import io
            import sys

            buf = io.StringIO()
            old = sys.stdout
            try:
                sys.stdout = buf
                rc = cmd_self_migrate(ns)
            finally:
                sys.stdout = old
            self.assertEqual(rc, 0)
            data = json.loads(buf.getvalue())
            self.assertTrue(data["ok"])
            self.assertEqual(data["would_write"], 1)


class VerifySelfMigrateTests(unittest.TestCase):
    def _core_ready_tree(self, root: Path, *, version: str = "0.7.2") -> None:
        (root / "AGENTS.md").write_text("# agents\n", encoding="utf-8")
        (root / "SPEC.md").write_text("# spec\n", encoding="utf-8")
        (root / "CURRENT.md").write_text("# current\n", encoding="utf-8")
        (root / ".plate").write_text(
            json.dumps(
                {
                    "version": "1.2",
                    "methodology": {},
                    "autonomy": {"enabled": False, "risk_tolerance": "off"},
                }
            ),
            encoding="utf-8",
        )
        (root / "VERSION").write_text(f"{version}\n", encoding="utf-8")
        goals = root / "docs" / "wiki"
        goals.mkdir(parents=True, exist_ok=True)
        (goals / "Goals.md").write_text("# Goals\n", encoding="utf-8")
        unreleased = root / ".agentic" / "releases" / "unreleased"
        unreleased.mkdir(parents=True, exist_ok=True)
        (unreleased / "README.md").write_text("x\n", encoding="utf-8")
        gh = root / ".github"
        (gh / "workflows").mkdir(parents=True, exist_ok=True)
        (gh / "labels.yml").write_text("labels: []\n", encoding="utf-8")
        (gh / "workflows" / "plate-ci.yml").write_text("name: plate\n", encoding="utf-8")

    def test_verify_ready_when_no_drift_and_core_ready(self):
        """Proves: offline verify ready when pin matches and adoption core_ready (#965)."""
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._core_ready_tree(root, version="0.7.2")
            report = verify_self_migrate(root, target_version="0.7.2")
        self.assertTrue(report["ok"])
        self.assertEqual(report["mode"], "verify")
        self.assertTrue(report["ready"])
        self.assertEqual(report["failures"], [])
        ids = {c["id"] for c in report["checks"]}
        self.assertEqual(ids, {"no_drift", "adoption_core_ready", "plate_config_valid"})
        self.assertFalse(report["auto_apply"])

    def test_verify_fails_on_pin_drift(self):
        """Proves: pin behind target fails no_drift check (#965)."""
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._core_ready_tree(root, version="0.6.0")
            report = verify_self_migrate(root, target_version="0.7.2")
        self.assertTrue(report["ok"])
        self.assertFalse(report["ready"])
        self.assertIn("pin_or_payload_drift", report["failures"])
        drift_check = next(c for c in report["checks"] if c["id"] == "no_drift")
        self.assertFalse(drift_check["ok"])

    def test_verify_fails_when_adoption_not_ready(self):
        """Proves: empty tree fails adoption_core_ready (#965)."""
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "VERSION").write_text("0.7.2\n", encoding="utf-8")
            report = verify_self_migrate(root, target_version="0.7.2")
        self.assertFalse(report["ready"])
        self.assertIn("adoption_not_core_ready", report["failures"])

    def test_plan_step_six_points_at_verify(self):
        """Proves: plan step 6_verify references self-migrate --verify (#965)."""
        with TemporaryDirectory() as tmp:
            report = plan_self_migrate(tmp, target_version="0.7.2")
        step = next(s for s in report["steps"] if s["id"] == "6_verify")
        self.assertIn("--verify", step["description"])

    def test_cmd_verify_json(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._core_ready_tree(root, version="0.7.2")
            ns = type(
                "NS",
                (),
                {
                    "repo_root": str(root),
                    "target_version": "0.7.2",
                    "no_payload": False,
                    "plan": False,
                    "json": True,
                    "merge_markers": False,
                    "apply_markers": False,
                    "upstream_dir": None,
                    "path": None,
                    "resolve_upstream": False,
                    "allow_network": False,
                    "pr_plan": False,
                    "apply_pr": False,
                    "allow_high_risk": False,
                    "base": "release",
                    "closes": None,
                    "verify": True,
                },
            )()
            import io
            import sys

            buf = io.StringIO()
            old = sys.stdout
            try:
                sys.stdout = buf
                rc = cmd_self_migrate(ns)
            finally:
                sys.stdout = old
            self.assertEqual(rc, 0)
            data = json.loads(buf.getvalue())
            self.assertTrue(data["ready"])
            self.assertEqual(data["mode"], "verify")


if __name__ == "__main__":
    unittest.main()
