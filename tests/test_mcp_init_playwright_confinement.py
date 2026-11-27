"""Playwright init write-path confinement (#1475)."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from plate_core.mcp.tools import InitPlaywrightTool


class InitPlaywrightConfinementTests(unittest.TestCase):
    @patch("plate_core.mcp.tools.resolve_template_source_root")
    def test_symlink_dst_blocks_before_copy(self, mock_template):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "checkout"
            repo.mkdir()
            outside = Path(tmp).parent / "mcp-init-pw-out"
            outside.mkdir(exist_ok=True)
            leak = outside / "playwright.config.ts"
            leak.write_text("//outside\n", encoding="utf-8")
            dst = repo / "playwright.config.ts"
            try:
                dst.symlink_to(leak)
            except OSError as exc:
                self.skipTest(f"symlink not permitted: {exc}")
            tpl = root / "template"
            tpl.mkdir()
            (tpl / "playwright.config.ts").write_text("//tpl\n", encoding="utf-8")
            mock_template.return_value = tpl
            result = InitPlaywrightTool.execute(
                str(repo),
                repo_root=root,
            )
            self.assertEqual(result["status"], "error")
            self.assertIn("repository root", result["message"].lower())


if __name__ == "__main__":
    unittest.main()