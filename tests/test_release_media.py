"""Tests for release notes media (#635)."""

from __future__ import annotations

import unittest

from plate_core.release import build_release, fragment_to_entry
from plate_core.release_media import (
    build_media_manifest,
    collect_release_media,
    decide_media_item,
    extract_media_from_fragment,
    media_approval_summary,
    media_feed_items,
    normalize_media_item,
    render_media_markdown,
)


class TestNormalize(unittest.TestCase):
    def test_path_and_url(self):
        m = normalize_media_item(
            {"path": "tests/e2e/fixtures/gifs/foo.gif", "caption": "Demo", "type": "gif"}
        )
        self.assertEqual(m["type"], "gif")
        self.assertEqual(m["approval_status"], "pending")
        m2 = normalize_media_item("https://example.com/x.mp4")
        self.assertEqual(m2["type"], "video")
        self.assertTrue(m2["url"])


class TestCollectRender(unittest.TestCase):
    def test_extract_and_markdown(self):
        frag = {
            "slug": "cool-feature",
            "change_type": "feature",
            "media": [
                {
                    "type": "gif",
                    "path": "tests/e2e/fixtures/gifs/cool.gif",
                    "caption": "Cool demo",
                    "approval_status": "approved",
                }
            ],
        }
        media = extract_media_from_fragment(frag)
        self.assertEqual(len(media), 1)
        md = render_media_markdown(media, only_approved=True)
        self.assertIn("Cool demo", md)
        self.assertIn("cool.gif", md)

    def test_manifest_and_feed(self):
        frags = [
            {
                "slug": "a",
                "media": [{"path": "x.gif", "caption": "A"}],
            },
            {
                "slug": "b",
                "media": [
                    {
                        "url": "https://ex.com/v.mp4",
                        "type": "video",
                        "caption": "B",
                        "approval_status": "approved",
                    }
                ],
            },
        ]
        man = build_media_manifest(frags, version="v1.0.0")
        self.assertEqual(man["summary"]["n_total"], 2)
        self.assertEqual(man["summary"]["n_pending"], 1)
        feed = media_feed_items(man["media"])
        self.assertEqual(len(feed), 1)

    def test_decide(self):
        media = collect_release_media(
            [{"slug": "s", "media": [{"path": "a.gif", "caption": "x"}]}]
        )
        out = decide_media_item(media, path="a.gif", decision="approve")
        self.assertTrue(out["ok"])
        self.assertEqual(out["media"][0]["approval_status"], "approved")


class TestFragmentEntry(unittest.TestCase):
    def test_fragment_to_entry_includes_media(self):
        entry = fragment_to_entry(
            {
                "change_type": "feature",
                "surface": "x",
                "migration_impact": "m",
                "agent_notes": "n",
                "media": [{"path": "demo.gif", "caption": "D"}],
            }
        )
        self.assertIn("media", entry)
        self.assertEqual(entry["media"][0]["path"], "demo.gif")

    def test_build_release_media_block(self):
        rel = build_release(
            "v9.9.9",
            [
                {
                    "slug": "s",
                    "change_type": "feature",
                    "surface": "s",
                    "migration_impact": "m",
                    "agent_notes": "n",
                    "_source_file": "s.json",
                    "media": [
                        {
                            "path": "g.gif",
                            "caption": "G",
                            "approval_status": "approved",
                        }
                    ],
                }
            ],
        )
        self.assertTrue(rel.get("media"))
        self.assertIn("media_markdown", rel)


if __name__ == "__main__":
    unittest.main()
