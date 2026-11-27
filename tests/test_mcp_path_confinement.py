"""Tests for MCP path confinement (#1475)."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from plate_core.mcp.path_confinement import PathConfinementError, confined


class McpPathConfinementTests(unittest.TestCase):
    def test_relative_path_stays_under_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            got = confined("src", root)
            self.assertEqual(got, (root / "src").resolve())

    def test_absolute_path_inside_root_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inner = root / "nested"
            inner.mkdir()
            got = confined(inner, root)
            self.assertEqual(got, inner.resolve())

    def test_escape_outside_root_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            outside = Path(tmp).parent / "outside-plate-mcp"
            outside.mkdir(exist_ok=True)
            with self.assertRaises(PathConfinementError) as ctx:
                confined(outside, root)
            self.assertNotIn(str(root), str(ctx.exception))
            self.assertNotIn(str(outside), str(ctx.exception))

    def test_symlink_escape_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            secret = root.parent / "secret-outside"
            secret.mkdir(exist_ok=True)
            link = root / "escape-link"
            try:
                link.symlink_to(secret, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"symlink not permitted in environment: {exc}")
            with self.assertRaises(PathConfinementError):
                confined(link, root)

    def test_dot_defaults_to_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(confined(".", root), root.resolve())


if __name__ == "__main__":
    unittest.main()