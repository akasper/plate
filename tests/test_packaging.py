"""Tests for marketplace packaging + media/adoption proof (#652)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from plate_core.packaging import (
    assess_package_readiness,
    build_onboarding_proof,
    build_package,
    build_user_narratives,
    decide_package_publish,
    list_packages,
    narrative_for_fragment,
    packaging_feed_items,
    plan_marketplace_package_op,
    render_package_markdown,
)


class TestNarratives(unittest.TestCase):
    def test_narrative_and_links(self):
        frag = {
            "slug": "cool-feature",
            "change_type": "feature",
            "summary": "Harden feed ranking for budget gates",
            "surface": "src/plate_core/feed.py",
            "links": ["#653", "654", "https://example.com/x"],
            "media": [{"path": "x.gif"}],
        }
        n = narrative_for_fragment(frag)
        self.assertIn("feed ranking", n["what_it_means"])
        self.assertIn("#653", n["links"])
        self.assertIn("#654", n["links"])
        self.assertEqual(n["media_count"], 1)

    def test_build_user_narratives(self):
        rows = build_user_narratives(
            [
                {"slug": "a", "summary": "Adds X"},
                {"slug": "b", "agent_notes": "Internal only note."},
            ]
        )
        self.assertEqual(len(rows), 2)
        self.assertTrue(rows[0]["what_it_means"])


class TestOnboarding(unittest.TestCase):
    def test_onboarding_proof_commands(self):
        proof = build_onboarding_proof("0.8.0")
        self.assertIn("0.8.0", proof["steps"][0])
        self.assertTrue(any("feed" in s.lower() for s in proof["steps"]))
        self.assertIn("gh plate feed --json", proof["proof_commands"])


class TestBuildPackage(unittest.TestCase):
    def test_build_persist_decide_feed(self):
        frags = [
            {
                "slug": "652-packaging",
                "change_type": "feature",
                "summary": "Marketplace packaging treats media as first-class",
                "links": ["#652", "#635"],
                "media": [
                    {
                        "path": "demo.gif",
                        "caption": "Demo",
                        "type": "gif",
                        "approval_status": "approved",
                    }
                ],
            },
            {
                "slug": "empty-docs",
                "change_type": "docs",
                "summary": "Docs polish",
            },
        ]
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            out = build_package("0.8.0", frags, base_dir=base, persist=True)
            self.assertTrue(out["ok"])
            pkg = out["package"]
            self.assertEqual(pkg["version"], "0.8.0")
            self.assertEqual(len(pkg["narratives"]), 2)
            self.assertTrue(pkg["onboarding_proof"]["steps"])
            self.assertIn("human_publish_task_required", pkg["readiness"]["blockers"])
            self.assertFalse(pkg["readiness"]["ready_to_publish"])
            self.assertIn(pkg["status"], ("pending_publish_approval", "ready", "draft"))

            rows = list_packages(base_dir=base)
            self.assertEqual(len(rows), 1)

            md = render_package_markdown(pkg)
            self.assertIn("marketplace package v0.8.0", md)
            self.assertIn("What this means for end users", md)
            self.assertIn("Install this and start the first Q&A", md)
            self.assertIn("#652", md)

            feed = packaging_feed_items(base_dir=base)
            self.assertTrue(feed)
            self.assertEqual(feed[0]["item_type"], "packaging")
            self.assertIn("ask_user_question", feed[0])

            decided = decide_package_publish(
                pkg["id"], "approve", decided_by="test", base_dir=base
            )
            self.assertTrue(decided["ok"])
            self.assertEqual(decided["package"]["status"], "approved_for_publish")
            # still never ready_to_publish
            self.assertFalse(
                (decided["package"].get("readiness") or {}).get("ready_to_publish")
            )

            feed2 = packaging_feed_items(base_dir=base)
            self.assertTrue(any("human" in (f.get("title") or "").lower() for f in feed2))

    def test_readiness_blockers(self):
        onb = build_onboarding_proof("1.0.0")
        r = assess_package_readiness(
            media=[],
            narratives=[],
            onboarding=onb,
        )
        self.assertIn("no_fragments_or_narratives", r["blockers"])
        self.assertIn("human_publish_task_required", r["blockers"])
        self.assertFalse(r["ready_to_publish"])

    def test_plan_op(self):
        plan = plan_marketplace_package_op(
            "0.8.0",
            fragments=[{"slug": "x", "summary": "Y"}],
        )
        self.assertTrue(plan["ok"])
        self.assertEqual(plan["op_id"], "marketplace-package")
        self.assertIn("plate_packaging_build", plan["tools"])


if __name__ == "__main__":
    unittest.main()
