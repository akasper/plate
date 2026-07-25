"""Tests for per-Feature media capture + approval (#636)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from plate_core.feature_media import (
    attach_to_fragment_file,
    decide_feature_media,
    feature_media_feed_items,
    list_feature_media,
    plan_feature_media,
    register_capture,
    skip_feature_media,
    slugify_test_name,
    to_fragment_media_entry,
)


class TestSlug(unittest.TestCase):
    def test_slugify(self):
        s = slugify_test_name("Cool Feature!", 12)
        self.assertTrue(s.replace("-", "").replace("_", "").isalnum())
        self.assertIn("12", s)


class TestLifecycle(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.base = Path(self._td.name)
        self.repo = Path(self._td.name) / "repo"
        self.repo.mkdir()
        (self.repo / "tests" / "e2e" / "fixtures" / "gifs").mkdir(parents=True)

    def tearDown(self):
        self._td.cleanup()

    def test_plan_register_approve_attach(self):
        p = plan_feature_media(
            feature_number=42,
            feature_title="AI coach pathway",
            base_dir=self.base,
        )
        self.assertTrue(p["ok"])
        rid = p["record"]["id"]
        tname = p["record"]["test_name"]
        gif = self.repo / "tests" / "e2e" / "fixtures" / "gifs" / f"{tname}.gif"
        gif.write_bytes(b"GIF89a-fake")
        reg = register_capture(
            rid,
            gif_path=str(gif),
            size_bytes=gif.stat().st_size,
            base_dir=self.base,
            repo_root=self.repo,
        )
        self.assertTrue(reg["ok"])
        self.assertEqual(reg["record"]["status"], "pending_approval")
        self.assertTrue(reg["file_exists"])

        feed = feature_media_feed_items(base_dir=self.base)
        self.assertTrue(any(x["id"] == rid for x in feed))

        dec = decide_feature_media(rid, "approve", base_dir=self.base)
        self.assertEqual(dec["record"]["status"], "approved")
        entry = to_fragment_media_entry(dec["record"])
        self.assertEqual(entry["approval_status"], "approved")

        frag = self.repo / "frag.json"
        frag.write_text(
            json.dumps(
                {
                    "slug": "ai-coach",
                    "change_type": "feature",
                    "surface": "x",
                    "migration_impact": "m",
                    "agent_notes": "n",
                }
            ),
            encoding="utf-8",
        )
        att = attach_to_fragment_file(rid, frag, base_dir=self.base)
        self.assertTrue(att["ok"])
        data = json.loads(frag.read_text(encoding="utf-8"))
        self.assertTrue(data.get("media"))
        self.assertEqual(list_feature_media(status="attached", base_dir=self.base)[0]["id"], rid)

    def test_skip(self):
        p = plan_feature_media(feature_title="X", base_dir=self.base)
        rid = p["record"]["id"]
        s = skip_feature_media(rid, base_dir=self.base)
        self.assertEqual(s["record"]["status"], "skipped")


if __name__ == "__main__":
    unittest.main()
