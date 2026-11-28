"""Playwright init write-path confinement (#1475)."""
from __future__ import annotations

import json
import tempfile
import unittest
from collections.abc import Callable
from pathlib import Path
from unittest.mock import patch

from plate_core.mcp.tools import InitPlaywrightTool


class InitPlaywrightConfinementTests(unittest.TestCase):
    def _run_with_symlink_dst(
        self,
        setup_repo: Callable[[Path, Path], None],
        setup_template: Callable[[Path], None],
        *,
        force: bool = False,
    ) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "checkout"
            repo.mkdir()
            outside = Path(tmp).parent / "mcp-init-pw-out"
            outside.mkdir(exist_ok=True)
            try:
                setup_repo(repo, outside)
            except OSError as exc:
                self.skipTest(f"symlink not permitted: {exc}")
            tpl = root / "template"
            tpl.mkdir()
            setup_template(tpl)
            with patch(
                "plate_core.mcp.tools.resolve_template_source_root",
                return_value=tpl,
            ):
                return InitPlaywrightTool.execute(
                    str(repo),
                    force=force,
                    repo_root=root,
                )

    def _assert_blocked(self, result: dict) -> None:
        self.assertEqual(result["status"], "error")
        self.assertIn("repository root", result["message"].lower())

    def test_symlink_playwright_config_blocks_before_copy(self):
        def setup_repo(repo: Path, outside: Path) -> None:
            leak = outside / "playwright.config.ts"
            leak.write_text("//outside\n", encoding="utf-8")
            (repo / "playwright.config.ts").symlink_to(leak)

        def setup_template(tpl: Path) -> None:
            (tpl / "playwright.config.ts").write_text("//tpl\n", encoding="utf-8")

        self._assert_blocked(self._run_with_symlink_dst(setup_repo, setup_template))

    def test_symlink_tests_e2e_blocks_before_copytree(self):
        def setup_repo(repo: Path, outside: Path) -> None:
            (repo / "tests").mkdir(parents=True)
            (repo / "tests" / "e2e").symlink_to(outside, target_is_directory=True)

        def setup_template(tpl: Path) -> None:
            e2e = tpl / "tests" / "e2e"
            e2e.mkdir(parents=True)
            (e2e / "smoke.spec.ts").write_text("//\n", encoding="utf-8")

        self._assert_blocked(
            self._run_with_symlink_dst(setup_repo, setup_template, force=True)
        )

    def test_symlink_script_dst_blocks_before_copy(self):
        def setup_repo(repo: Path, outside: Path) -> None:
            (outside / "e2e-record.sh").write_text("#!/bin/sh\n", encoding="utf-8")
            scripts = repo / "scripts"
            scripts.mkdir()
            (scripts / "e2e-record.sh").symlink_to(outside / "e2e-record.sh")

        def setup_template(tpl: Path) -> None:
            scripts = tpl / "scripts"
            scripts.mkdir()
            (scripts / "e2e-record.sh").write_text("#!/bin/sh\n", encoding="utf-8")

        self._assert_blocked(self._run_with_symlink_dst(setup_repo, setup_template))

    def test_symlink_scripts_dir_blocks_before_mkdir(self):
        def setup_repo(repo: Path, outside: Path) -> None:
            (repo / "scripts").symlink_to(outside, target_is_directory=True)

        def setup_template(tpl: Path) -> None:
            scripts = tpl / "scripts"
            scripts.mkdir()
            (scripts / "e2e-record.sh").write_text("#!/bin/sh\n", encoding="utf-8")

        self._assert_blocked(self._run_with_symlink_dst(setup_repo, setup_template))

    def test_symlink_package_json_blocks_before_update(self):
        def setup_repo(repo: Path, outside: Path) -> None:
            (outside / "package.json").write_text(
                json.dumps({"name": "leak"}), encoding="utf-8"
            )
            (repo / "package.json").symlink_to(outside / "package.json")

        def setup_template(tpl: Path) -> None:
            (tpl / "playwright.config.ts").write_text("//n\n", encoding="utf-8")

        self._assert_blocked(self._run_with_symlink_dst(setup_repo, setup_template))


if __name__ == "__main__":
    unittest.main()