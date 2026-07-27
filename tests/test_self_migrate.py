"""Tests for self-migrate dry-run plan and marker merge (#939/#943 / Epic #649)."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from plate_core.self_migrate import (
    plan_marker_merge,
    plan_self_migrate,
    resolve_upstream_version,
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


if __name__ == "__main__":
    unittest.main()
