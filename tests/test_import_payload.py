"""Tests for first-class template payload import (#616)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

# Manifest path_rules mark this as on_conflict: conflict (not preserve_existing).
_CONFLICT_FIXTURE_REL = "package.json"


def _seed_differing_payload_file(target: str | Path, rel: str = _CONFLICT_FIXTURE_REL) -> Path:
    """Apply payload once, then modify ``rel`` so conservative import reports a conflict."""
    from plate_core.import_payload import import_payload

    root = Path(target)
    applied = import_payload(root, strategy="safe", apply=True)
    dest = root / rel
    if not dest.is_file():
        created = applied.get("created") or []
        raise AssertionError(f"{rel!r} not found in {created}")
    dest.write_text(dest.read_text(encoding="utf-8") + "\n# local change\n", encoding="utf-8")
    return dest


class TestImportPayload(unittest.TestCase):
    def test_dry_run_empty_target_creates_plan(self):
        from plate_core.import_payload import import_payload, list_payload_relative_paths

        paths = list_payload_relative_paths()
        self.assertGreater(len(paths), 0)

        with tempfile.TemporaryDirectory() as tmp:
            report = import_payload(tmp, strategy="safe", dry_run=True)
            self.assertTrue(report["ok"])
            self.assertFalse(report["apply_mode"])
            self.assertEqual(report["strategy"], "safe")
            self.assertGreater(report["counts"]["would_create"], 0)
            self.assertEqual(report["counts"]["created"], 0)
            # no side effects
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_safe_apply_then_skip_identical(self):
        from plate_core.import_payload import import_payload

        with tempfile.TemporaryDirectory() as tmp:
            first = import_payload(tmp, strategy="safe", apply=True)
            self.assertTrue(first["ok"])
            self.assertGreater(first["counts"]["created"], 0)
            # files exist
            sample = first["created"][0]
            self.assertTrue((Path(tmp) / sample).is_file())

            second = import_payload(tmp, strategy="safe", dry_run=True)
            self.assertGreater(second["counts"]["would_skip"], 0)
            self.assertEqual(second["counts"]["would_create"], 0)

    def test_conservative_conflict_on_differ(self):
        from plate_core.import_payload import import_payload

        with tempfile.TemporaryDirectory() as tmp:
            rel = _CONFLICT_FIXTURE_REL
            dest = _seed_differing_payload_file(tmp, rel)

            report = import_payload(tmp, strategy="conservative", dry_run=True)
            self.assertIn(rel, report["would_conflict"])
            apply_report = import_payload(tmp, strategy="conservative", apply=True)
            self.assertIn(rel, apply_report["conflicts"])
            # still has local marker
            self.assertIn("local change", dest.read_text(encoding="utf-8"))

    def test_conservative_taxonomy_templates_conflict_not_overwrite(self):
        """#1250: customized labels/templates must survive conservative --apply."""
        from plate_core.import_payload import import_payload

        taxonomy_paths = (
            ".github/labels.yml",
            ".github/ISSUE_TEMPLATE/feature.yml",
            ".github/PULL_REQUEST_TEMPLATE.md",
        )
        markers = {
            ".github/labels.yml": "# adopter area taxonomy\n",
            ".github/ISSUE_TEMPLATE/feature.yml": "# customized feature template\n",
            ".github/PULL_REQUEST_TEMPLATE.md": "# customized pr template\n",
        }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            import_payload(root, strategy="safe", apply=True)
            for rel in taxonomy_paths:
                dest = root / rel
                self.assertTrue(dest.is_file(), msg=f"missing after seed: {rel}")
                dest.write_text(
                    markers[rel] + dest.read_text(encoding="utf-8"),
                    encoding="utf-8",
                )

            dry = import_payload(root, strategy="conservative", dry_run=True)
            self.assertTrue(dry["ok"])
            for rel in taxonomy_paths:
                self.assertIn(rel, dry["would_conflict"], msg=dry.get("files"))
                self.assertNotIn(rel, dry["would_overwrite"])
            self.assertEqual(dry["counts"]["would_overwrite"], 0)

            applied = import_payload(root, strategy="conservative", apply=True)
            self.assertTrue(applied["ok"])
            for rel in taxonomy_paths:
                self.assertIn(rel, applied["conflicts"])
                self.assertNotIn(rel, applied.get("overwritten") or [])
                self.assertIn(markers[rel].strip(), (root / rel).read_text(encoding="utf-8"))

    def test_force_overwrites(self):
        from plate_core.import_payload import import_payload

        with tempfile.TemporaryDirectory() as tmp:
            first = import_payload(tmp, strategy="safe", apply=True)
            rel = first["created"][0]
            dest = Path(tmp) / rel
            original = dest.read_bytes()
            dest.write_bytes(b"totally different content")

            report = import_payload(tmp, strategy="force", apply=True)
            self.assertIn(rel, report["overwritten"])
            self.assertEqual(dest.read_bytes(), original)

    def test_invalid_strategy(self):
        from plate_core.import_payload import import_payload

        with tempfile.TemporaryDirectory() as tmp:
            report = import_payload(tmp, strategy="nope", dry_run=True)
            self.assertFalse(report["ok"])
            self.assertIn("Invalid strategy", report["error"] or "")

    def test_escape_hatch_writes_plan_and_draft_pr_body(self):
        """#622: hard-merge escape hatch never writes payload; emits review artifacts."""
        from plate_core.import_payload import import_payload, write_import_escape_hatch

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "tgt"
            hatch = Path(tmp) / "hatch"
            target.mkdir()
            rel = _CONFLICT_FIXTURE_REL
            _seed_differing_payload_file(target, rel)
            report = import_payload(
                target,
                strategy="conservative",
                dry_run=True,
                escape_hatch_dir=hatch,
            )
            self.assertTrue(report["ok"])
            self.assertIn(rel, report["would_conflict"])
            eh = report.get("escape_hatch") or {}
            self.assertTrue(eh.get("ok"))
            self.assertTrue(Path(eh["plan_json"]).is_file())
            self.assertTrue(Path(eh["plan_md"]).is_file())
            self.assertTrue(Path(eh["draft_pr_body"]).is_file())
            body = Path(eh["draft_pr_body"]).read_text(encoding="utf-8")
            self.assertIn("Payload additions", body)
            self.assertIn("Human review checklist", body)
            self.assertIn("Conflicts requiring judgment", body)
            # payload not force-written by hatch
            self.assertIn("local", (target / rel).read_text(encoding="utf-8"))

    def test_escape_hatch_on_conflict_default_dir(self):
        from plate_core.import_payload import import_payload

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "tgt"
            target.mkdir()
            rel = _CONFLICT_FIXTURE_REL
            dest = _seed_differing_payload_file(target, rel)
            dest.write_text("changed\n", encoding="utf-8")
            report = import_payload(
                target,
                strategy="conservative",
                dry_run=True,
                escape_hatch_on_conflict=True,
            )
            eh = report.get("escape_hatch") or {}
            self.assertTrue(eh.get("has_conflicts"))
            self.assertTrue((target / ".agentic" / "import-escape-hatch" / "plan.json").is_file())

    def test_cli_dry_run_json(self):
        import argparse
        from io import StringIO
        from unittest.mock import patch

        from plate_core import cli as cli_mod

        with tempfile.TemporaryDirectory() as tmp:
            args = argparse.Namespace(
                target_dir=tmp,
                strategy="safe",
                template_repo=None,
                apply=False,
                json=True,
            )
            buf = StringIO()
            with patch("sys.stdout", buf):
                rc = cli_mod.cmd_import_payload(args)
            self.assertEqual(rc, 0)
            data = json.loads(buf.getvalue())
            self.assertTrue(data["ok"])
            self.assertGreater(data["counts"]["would_create"], 0)

    def test_parser_registers_import_payload(self):
        from plate_core.cli import build_parser

        help_text = build_parser().format_help()
        self.assertIn("import-payload", help_text)

    def test_cli_namespace_docs_tri_state(self):
        """--namespace-docs / --no-namespace-docs reach import_payload (#1016)."""
        import argparse
        from io import StringIO
        from unittest.mock import patch

        from plate_core.cli import build_parser, cmd_import_payload

        parser = build_parser()
        with tempfile.TemporaryDirectory() as tmp:
            docs = Path(tmp) / "docs"
            docs.mkdir()
            (docs / "README.md").write_text("# Product handbook\n", encoding="utf-8")

            forced = parser.parse_args(
                ["import-payload", "--target-dir", tmp, "--namespace-docs", "--json"]
            )
            self.assertIsInstance(forced, argparse.Namespace)
            buf = StringIO()
            with patch("sys.stdout", buf):
                self.assertEqual(cmd_import_payload(forced), 0)
            self.assertTrue(json.loads(buf.getvalue())["namespace_docs"])

            suppressed = parser.parse_args(
                ["import-payload", "--target-dir", tmp, "--no-namespace-docs", "--json"]
            )
            buf = StringIO()
            with patch("sys.stdout", buf):
                self.assertEqual(cmd_import_payload(suppressed), 0)
            self.assertFalse(json.loads(buf.getvalue())["namespace_docs"])

    def test_copy_template_payload_local_alias(self):
        """#620: bootstrap/agents can call copy_template_payload_local."""
        from plate_core.import_payload import copy_template_payload_local

        with tempfile.TemporaryDirectory() as tmp:
            report = copy_template_payload_local(tmp, dry_run=True)
            self.assertTrue(report["ok"])
            self.assertGreater(report["counts"]["would_create"], 0)
            applied = copy_template_payload_local(tmp, dry_run=False, strategy="safe")
            self.assertGreater(applied["counts"]["created"], 0)

    def test_bootstrap_shares_payload_path_planner(self):
        """#620: bootstrap remote applier uses same relative path set as local."""
        from plate_core.bootstrap import _template_payload_relative_paths
        from plate_core.import_payload import list_payload_relative_paths
        from plate_core.template_payload import resolve_template_source

        root, _ = resolve_template_source()
        self.assertEqual(
            _template_payload_relative_paths(root),
            list_payload_relative_paths(root),
        )

    def test_ci_yml_install_as_on_conflict(self):
        """#617: existing product ci.yml → write plate-ci.yml, preserve original."""
        from plate_core.import_payload import import_payload

        with tempfile.TemporaryDirectory() as tmp:
            ci = Path(tmp) / ".github" / "workflows" / "ci.yml"
            ci.parent.mkdir(parents=True, exist_ok=True)
            ci.write_text("# product CI\n", encoding="utf-8")

            report = import_payload(tmp, strategy="safe", apply=True)
            self.assertTrue(report["ok"])
            # original preserved
            self.assertEqual(ci.read_text(encoding="utf-8"), "# product CI\n")
            plate_ci = Path(tmp) / ".github" / "workflows" / "plate-ci.yml"
            self.assertTrue(plate_ci.is_file(), msg=report["created"][:10])
            # decision recorded
            decisions = [f for f in report["files"] if f["path"] == ".github/workflows/ci.yml"]
            self.assertEqual(len(decisions), 1)
            self.assertIn(decisions[0]["action"], ("create_as", "create"))
            if decisions[0]["action"] == "create_as":
                self.assertEqual(
                    decisions[0]["target_path"], ".github/workflows/plate-ci.yml"
                )

    def test_conservative_ci_yml_conflict_not_second_workflow(self):
        """#1264: conservative import must not plan plate-ci.yml when ci.yml exists."""
        from plate_core.import_payload import import_payload

        with tempfile.TemporaryDirectory() as tmp:
            ci = Path(tmp) / ".github" / "workflows" / "ci.yml"
            ci.parent.mkdir(parents=True, exist_ok=True)
            ci.write_text("# product CI\n", encoding="utf-8")

            dry = import_payload(tmp, strategy="conservative", dry_run=True)
            self.assertTrue(dry["ok"])
            ci_create = [
                x
                for x in dry["would_create"]
                if "plate-ci.yml" in x or x.endswith("workflows/ci.yml")
            ]
            self.assertEqual(ci_create, [], msg=dry["would_create"][:20])
            self.assertIn(".github/workflows/ci.yml", dry["would_conflict"])

            applied = import_payload(tmp, strategy="conservative", apply=True)
            plate_ci = Path(tmp) / ".github" / "workflows" / "plate-ci.yml"
            self.assertFalse(plate_ci.exists())
            self.assertIn(".github/workflows/ci.yml", applied["conflicts"])

    def test_seeds_current_md_when_missing(self):
        """#618: import seeds CURRENT.md when absent; skips when present."""
        from plate_core.import_payload import import_payload

        with tempfile.TemporaryDirectory() as tmp:
            dry = import_payload(tmp, strategy="safe", dry_run=True)
            self.assertIn("CURRENT.md", dry["would_create"])
            self.assertFalse((Path(tmp) / "CURRENT.md").exists())

            applied = import_payload(tmp, strategy="safe", apply=True)
            self.assertIn("CURRENT.md", applied["created"])
            text = (Path(tmp) / "CURRENT.md").read_text(encoding="utf-8")
            self.assertIn("Adoption note", text)
            self.assertIn(".agentic/releases/", text)
            self.assertNotIn(
                "Project-specific CI commands are not defined by the generic template",
                text,
            )

            again = import_payload(tmp, strategy="safe", dry_run=True)
            self.assertIn("CURRENT.md", again["would_skip"])

    def test_seeds_project_readme_stub_not_template_readme(self):
        """#1188: import seeds a project README stub; never copies template README."""
        from plate_core.import_payload import import_payload

        with tempfile.TemporaryDirectory(prefix="coacharino-") as tmp:
            dry = import_payload(tmp, strategy="conservative", dry_run=True)
            self.assertIn("README.md", dry["would_create"])
            self.assertNotIn("README.md", dry.get("would_conflict") or [])

            applied = import_payload(tmp, strategy="conservative", apply=True)
            self.assertIn("README.md", applied["created"])
            text = (Path(tmp) / "README.md").read_text(encoding="utf-8")
            self.assertIn("Built with [PLATE]", text)
            self.assertNotIn("# PLATE Template", text)
            self.assertNotIn("plate_template", text.lower())
            self.assertIn("# coacharino-", text.splitlines()[0])

    def test_preserves_existing_root_readme(self):
        """#1188: an existing README is left unchanged."""
        from plate_core.import_payload import import_payload

        with tempfile.TemporaryDirectory() as tmp:
            custom = "# My product\n\nShip the thing.\n"
            (Path(tmp) / "README.md").write_text(custom, encoding="utf-8")
            applied = import_payload(tmp, strategy="safe", apply=True)
            self.assertIn("README.md", applied.get("skipped") or applied.get("would_skip"))
            self.assertEqual((Path(tmp) / "README.md").read_text(encoding="utf-8"), custom)

    def test_readme_stub_uses_github_description_when_available(self):
        """#1188: gh repo metadata enriches the seeded README when reachable."""
        from unittest.mock import MagicMock, patch

        from plate_core.import_payload import (
            build_project_readme_stub,
            import_payload,
            resolve_project_readme_context,
        )

        gh = MagicMock()
        gh.api.return_value = {
            "name": "coacharino",
            "description": "Coaching platform for teams.",
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch(
                "plate_core.import_payload._repo_slug_from_target",
                return_value="akasper/coacharino",
            ):
                name, desc = resolve_project_readme_context(
                    root,
                    gh=gh,
                    fetch_github=True,
                )
            self.assertEqual(name, "coacharino")
            self.assertEqual(desc, "Coaching platform for teams.")
            stub = build_project_readme_stub(repo_name=name, description=desc)
            self.assertIn("Coaching platform for teams.", stub)

            with patch(
                "plate_core.import_payload.resolve_project_readme_context",
                return_value=("coacharino", "Coaching platform for teams."),
            ):
                applied = import_payload(root, strategy="safe", apply=True)
            self.assertIn("README.md", applied["created"])
            self.assertIn(
                "Coaching platform for teams.",
                (root / "README.md").read_text(encoding="utf-8"),
            )

    def test_seeds_releases_and_plate_for_core_ready(self):
        """Import seeds releases layout + .plate so offline core_ready is reachable."""
        from plate_core.import_payload import import_payload
        from plate_core.adoption import assess_adoption_readiness
        from plate_core.plate_config import get_plate_config_report

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dry = import_payload(tmp, strategy="safe", dry_run=True)
            self.assertIn(
                ".agentic/releases/unreleased/README.md",
                dry["would_create"],
            )
            self.assertIn(".plate", dry["would_create"])
            applied = import_payload(tmp, strategy="safe", apply=True)
            self.assertIn(
                ".agentic/releases/unreleased/README.md",
                applied["created"],
            )
            self.assertIn(".plate", applied["created"])
            self.assertTrue(
                (root / ".agentic" / "releases" / "unreleased" / "README.md").is_file()
            )
            self.assertTrue((root / ".plate").is_file())
            # JSON schema (not YAML)
            self.assertTrue(
                (root / ".plate").read_text(encoding="utf-8").lstrip().startswith("{")
            )
            rep = get_plate_config_report(root)
            self.assertTrue(rep.valid, msg=getattr(rep, "errors", None))
            # Second apply must not clobber custom .plate
            (root / ".plate").write_text(
                (root / ".plate").read_text(encoding="utf-8").replace(
                    '"risk_tolerance": "medium"',
                    '"risk_tolerance": "off"',
                ),
                encoding="utf-8",
            )
            again = import_payload(tmp, strategy="safe", apply=True)
            self.assertIn(".plate", again["skipped"] or again["would_skip"])
            self.assertIn('"risk_tolerance": "off"', (root / ".plate").read_text(encoding="utf-8"))
            ready = assess_adoption_readiness(root, include_optional=False)
            checks = {c["id"]: c["ok"] for c in ready.get("checks") or []}
            self.assertTrue(
                checks.get("agentic_releases"),
                msg=f"expected agentic_releases ok: {ready.get('checks')}",
            )
            self.assertTrue(checks.get("plate_config"), msg=ready.get("checks"))
            self.assertTrue(ready.get("core_ready"), msg=ready)

    def test_next_command_dry_run_with_creates(self):
        """Adopter path: dry-run with pending creates points at --apply (same strategy)."""
        from plate_core.import_payload import import_payload

        with tempfile.TemporaryDirectory() as tmp:
            report = import_payload(tmp, strategy="conservative", dry_run=True)
            self.assertTrue(report["ok"])
            self.assertGreater(report["counts"]["would_create"], 0)
            self.assertEqual(
                report["next_command"],
                "gh plate import-payload --apply --strategy conservative",
            )
            self.assertTrue(
                any("Next command:" in s for s in report["next_steps"]),
                msg=report["next_steps"][:3],
            )

    def test_next_command_dry_run_with_conflicts(self):
        """Conflicts → escape-hatch command, not silent force apply."""
        from plate_core.import_payload import import_payload

        with tempfile.TemporaryDirectory() as tmp:
            rel = _CONFLICT_FIXTURE_REL
            _seed_differing_payload_file(tmp, rel)
            report = import_payload(tmp, strategy="conservative", dry_run=True)
            self.assertTrue(report["would_conflict"])
            self.assertIn("--escape-hatch", report["next_command"])
            self.assertIn("conservative", report["next_command"])
            self.assertNotIn("--apply", report["next_command"])

    def test_next_command_after_apply(self):
        """Successful apply → bootstrap --adopt as the single next command."""
        from plate_core.import_payload import import_payload

        with tempfile.TemporaryDirectory() as tmp:
            report = import_payload(tmp, strategy="safe", apply=True)
            self.assertGreater(report["counts"]["created"], 0)
            self.assertIn("--repo OWNER/REPO", report["next_command"])
            self.assertIn("could not resolve owner/name", report["next_command"])

    def test_next_command_after_apply_resolves_git_origin(self):
        from plate_core.import_payload import import_payload
        from plate_core.procutil import run_hidden

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_hidden(["git", "init"], cwd=str(root), check=True)
            run_hidden(
                ["git", "remote", "add", "origin", "https://github.com/coacharino/adopted.git"],
                cwd=str(root),
                check=True,
            )
            report = import_payload(root, strategy="safe", apply=True)
            self.assertEqual(
                report["next_command"],
                "gh plate bootstrap --repo coacharino/adopted --adopt --apply",
            )

    def test_next_command_noop_points_at_adopt(self):
        """All payload present / skipped → adopt readiness, not re-apply."""
        from plate_core.import_payload import import_payload

        with tempfile.TemporaryDirectory() as tmp:
            import_payload(tmp, strategy="safe", apply=True)
            again = import_payload(tmp, strategy="safe", dry_run=True)
            self.assertEqual(again["counts"]["would_create"], 0)
            self.assertFalse(again["would_conflict"])
            self.assertEqual(again["next_command"], "gh plate adopt --json")

    def test_next_command_invalid_strategy(self):
        from plate_core.import_payload import import_payload

        with tempfile.TemporaryDirectory() as tmp:
            report = import_payload(tmp, strategy="nope", dry_run=True)
            self.assertFalse(report["ok"])
            self.assertIn("conservative", report["next_command"])
            self.assertIn("--dry-run", report["next_command"])

    def test_post_import_next_steps_never_suggest_config_init_when_plate_exists(self):
        """#1189: after apply seeds .plate, printed next steps must not mention config init."""
        from plate_core.import_payload import format_import_payload_report, import_payload

        with tempfile.TemporaryDirectory() as tmp:
            report = import_payload(tmp, strategy="conservative", apply=True)
            self.assertTrue((Path(tmp) / ".plate").is_file(), msg="expected seeded .plate")
            steps = report["next_steps"]
            joined = " ".join(steps) + " " + report.get("next_command", "")
            self.assertNotIn(
                "config init",
                joined.lower(),
                msg=f"unexpected config init in next_steps: {steps}",
            )
            formatted = format_import_payload_report(report)
            self.assertNotIn("config init", formatted.lower())


if __name__ == "__main__":
    unittest.main()
