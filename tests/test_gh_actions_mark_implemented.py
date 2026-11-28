"""Unit tests for gh_actions_mark_implemented.main (#1475)."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest.mock import patch

from plate_core import gh_actions_mark_implemented


class GhActionsMarkImplementedTests(unittest.TestCase):
    def test_missing_env_returns_one(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(gh_actions_mark_implemented.main(), 1)

    def test_non_integration_base_skips_cleanly(self):
        event = {
            "repository": {"owner": {"login": "o"}, "name": "r"},
            "pull_request": {"base": {"ref": "main"}, "body": "Closes #1", "number": 2},
        }
        with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as f:
            json.dump(event, f)
            path = f.name
        try:
            with patch.dict(
                os.environ,
                {"GITHUB_TOKEN": "t", "GITHUB_EVENT_PATH": path, "GITHUB_EVENT_NAME": "pull_request"},
                clear=True,
            ):
                self.assertEqual(gh_actions_mark_implemented.main(), 0)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()