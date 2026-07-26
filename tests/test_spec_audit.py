"""Tests for SPEC audit engine (#338)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path


class TestSpecAudit(unittest.TestCase):
    def test_missing_spec(self):
        from plate_core.spec_audit import audit_spec

        with tempfile.TemporaryDirectory() as tmp:
            r = audit_spec(tmp)
            self.assertFalse(r.ok)
            self.assertIn("not found", r.error or "")

    def test_undocumented_fragment_and_aligned(self):
        from plate_core.spec_audit import audit_spec

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "SPEC.md").write_text(
                "# Spec\n\n## AutonomyEngine\n\nThe AutonomyEngine runs budgeted cycles.\n"
                "See `src/plate_core/autonomy.py` and `.plate`.\n",
                encoding="utf-8",
            )
            # create cited path so not stale
            (root / "src" / "plate_core").mkdir(parents=True)
            (root / "src" / "plate_core" / "autonomy.py").write_text("# a\n", encoding="utf-8")
            (root / ".plate").write_text("{}\n", encoding="utf-8")

            unrel = root / ".agentic" / "releases" / "unreleased"
            unrel.mkdir(parents=True)
            (unrel / "autonomy-engine.json").write_text(
                json.dumps(
                    {
                        "slug": "autonomy-engine",
                        "change_type": "feature",
                        "surface": "src/plate_core/autonomy.py",
                        "summary": "AutonomyEngine budgeted cycles",
                        "migration_impact": "none",
                        "agent_notes": "n/a",
                    }
                ),
                encoding="utf-8",
            )
            (unrel / "mystery-widget.json").write_text(
                json.dumps(
                    {
                        "slug": "mystery-widget",
                        "change_type": "feature",
                        "surface": "src/plate_core/mystery_widget.py",
                        "summary": "Brand new mystery widget surface",
                        "migration_impact": "none",
                        "agent_notes": "n/a",
                    }
                ),
                encoding="utf-8",
            )

            r = audit_spec(root)
            self.assertTrue(r.ok)
            kinds = {f.kind for f in r.findings}
            self.assertIn("aligned", kinds)
            self.assertIn("undocumented", kinds)
            undoc = [f for f in r.findings if f.kind == "undocumented"]
            self.assertTrue(any("mystery-widget" in f.title for f in undoc))

    def test_stale_path_citation(self):
        from plate_core.spec_audit import audit_spec

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "SPEC.md").write_text(
                "# Spec\n\nEvidence at `docs/missing/does-not-exist.md`.\n",
                encoding="utf-8",
            )
            (root / ".agentic" / "releases" / "unreleased").mkdir(parents=True)
            r = audit_spec(root)
            self.assertTrue(r.ok)
            stale = [f for f in r.findings if f.kind == "stale_evidence"]
            self.assertTrue(any("does-not-exist" in f.title for f in stale))

    def test_cli_registers(self):
        from plate_core.cli import build_parser

        self.assertIn("spec-audit", build_parser().format_help())


if __name__ == "__main__":
    unittest.main()
