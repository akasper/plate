"""Tests for agent comment attribution (#1236)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from plate_core.comment_attribution import (
    DEFAULT_ATTRIBUTION_FORMAT,
    apply_comment_attribution,
    resolve_comment_attribution,
)
from plate_core.plate_config import validate_plate_config


class CommentAttributionTests(unittest.TestCase):
    def test_default_settings_enabled(self):
        settings = resolve_comment_attribution(autonomy={})
        self.assertTrue(settings["enabled"])
        self.assertIn("{agent}", settings["format"])

    def test_apply_prepends_header(self):
        out = apply_comment_attribution(
            "Fixed in abc123.",
            agent="Grok Bot",
            on_behalf_of="Andrew",
            enabled=True,
            format_template=DEFAULT_ATTRIBUTION_FORMAT,
        )
        self.assertTrue(out.startswith("🤖 Grok Bot on behalf of Andrew"))
        self.assertIn("Fixed in abc123.", out)

    def test_apply_respects_disabled(self):
        body = "No header please."
        self.assertEqual(
            apply_comment_attribution(body, agent="Grok Bot", enabled=False),
            body,
        )

    def test_apply_skips_empty_agent(self):
        body = "Plain comment."
        self.assertEqual(
            apply_comment_attribution(body, agent="  ", on_behalf_of="Andrew"),
            body,
        )

    def test_load_from_plate_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".plate").write_text(
                json.dumps(
                    {
                        "version": "1.3",
                        "autonomy": {
                            "comment_attribution": {
                                "enabled": False,
                                "format": "Agent:{agent} for {on_behalf_of}",
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            settings = resolve_comment_attribution(root)
            self.assertFalse(settings["enabled"])
            self.assertEqual(settings["format"], "Agent:{agent} for {on_behalf_of}")

    def test_plate_config_validation_accepts_comment_attribution(self):
        validate_plate_config(
            {
                "version": "1.3",
                "autonomy": {
                    "comment_attribution": {
                        "enabled": True,
                        "format": "🤖 {agent} on behalf of {on_behalf_of}",
                    }
                },
            },
            strict=True,
        )


if __name__ == "__main__":
    unittest.main()
