"""Tests for hybrid / non-code project support (#650)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from plate_core.hybrid import (
    detect_project_kind,
    feature_validation_plan,
    get_kind_contract,
    hybrid_feed_items,
    list_project_kinds,
    list_validation_strategies,
    load_project_profile,
    planning_template_for_kind,
    set_project_kind,
)


class TestCatalog(unittest.TestCase):
    def test_kinds_and_contracts(self):
        kinds = list_project_kinds()
        ids = {k["id"] for k in kinds}
        self.assertIn("software", ids)
        self.assertIn("marketing", ids)
        self.assertIn("hybrid", ids)
        self.assertIn("infra", ids)
        c = get_kind_contract("marketing")
        self.assertIsNotNone(c)
        assert c is not None
        self.assertIn("link_check", c["validation"])
        self.assertTrue(c["validation_details"])

    def test_validation_filter(self):
        rows = list_validation_strategies(kind="infra")
        ids = {r["id"] for r in rows}
        self.assertIn("plan_diff", ids)
        self.assertNotIn("seo_check", ids)


class TestDetectAndPersist(unittest.TestCase):
    def test_detect_docs_layout(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "docs").mkdir()
            (root / "mkdocs.yml").write_text("site_name: x\n", encoding="utf-8")
            out = detect_project_kind(root)
            self.assertTrue(out["ok"])
            self.assertEqual(out["profile"]["kind"], "docs")
            self.assertGreater(out["profile"]["confidence"], 0)

    def test_detect_hybrid_multi_surface(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
            (root / "src").mkdir()
            (root / "tests").mkdir()
            (root / "docs").mkdir()
            (root / "marketing").mkdir()
            out = detect_project_kind(root)
            self.assertIn(out["profile"]["kind"], ("hybrid", "software", "docs", "marketing"))
            # multi-surface should score hybrid high
            self.assertGreaterEqual(out["scores"].get("hybrid", 0), 2.0)

    def test_set_and_load(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            out = set_project_kind("content", base_dir=base, note="blog")
            self.assertTrue(out["ok"])
            loaded = load_project_profile(base_dir=base, detect_if_missing=False)
            self.assertTrue(loaded["ok"])
            self.assertEqual(loaded["profile"]["kind"], "content")
            self.assertEqual(loaded["source"], "persisted")


class TestPlanningAndValidation(unittest.TestCase):
    def test_template_and_plan(self):
        t = planning_template_for_kind("design_system")
        self.assertTrue(t["ok"])
        self.assertGreaterEqual(len(t["questions"]), 3)
        plan = feature_validation_plan(
            "design_system", feature_title="Button redesign"
        )
        self.assertTrue(plan["ok"])
        step_ids = {s["id"] for s in plan["steps"]}
        self.assertIn("visual_regression", step_ids)
        self.assertIn("design_contract", step_ids)

    def test_unknown_kind(self):
        self.assertFalse(planning_template_for_kind("nope")["ok"])
        self.assertIsNone(get_kind_contract("nope"))


class TestFeed(unittest.TestCase):
    def test_feed_when_non_software_detected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "docs").mkdir()
            (root / "mkdocs.yml").write_text("site_name: x\n", encoding="utf-8")
            items = hybrid_feed_items(base_dir=root / "hybrid", repo_root=root)
            self.assertTrue(items)
            self.assertTrue(any("ask_user_question" in i for i in items))
            self.assertTrue(any("docs" in (i.get("title") or "").lower() or "docs" in (i.get("badges") or []) for i in items))

    def test_feed_quiet_for_empty_software(self):
        with tempfile.TemporaryDirectory() as td:
            items = hybrid_feed_items(base_dir=Path(td) / "hybrid", repo_root=Path(td))
            self.assertEqual(items, [])


if __name__ == "__main__":
    unittest.main()
