"""Table-driven path confinement for every MCP tool path parameter (#1475)."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from plate_core.mcp.arg_confinement import (
    _OR_ALIAS_PATTERN,
    _dispatch_tool_blocks,
    all_registered_path_parameters,
    build_path_parameter_index,
    confine_tool_arguments,
    discover_handler_or_arg_aliases,
    uncovered_handler_path_aliases,
)
from plate_core.mcp.path_confinement import PathConfinementError, session_repo_root
from plate_core.mcp.tool_profiles import PROFILE_ALL, configure_mcp_tool_profiles, reset_mcp_tool_profile_session


class McpAllToolsPathConfinementTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["PLATE_MCP_TOOL_PROFILES"] = PROFILE_ALL
        reset_mcp_tool_profile_session()
        configure_mcp_tool_profiles(PROFILE_ALL)
        self.repo_root = session_repo_root()

    def tearDown(self) -> None:
        os.environ.pop("PLATE_MCP_TOOL_PROFILES", None)
        reset_mcp_tool_profile_session()

    def test_registry_lists_path_parameters(self):
        index = build_path_parameter_index()
        self.assertGreaterEqual(len(index), 50)
        self.assertGreaterEqual(len(all_registered_path_parameters()), 70)
        rows = set(all_registered_path_parameters())
        self.assertIn(("plate_feature_media_attach_fragment", "fragment"), rows)
        self.assertIn(("plate_self_migrate_merge_markers", "upstream_dir"), rows)

    def test_handler_path_aliases_are_registered(self):
        self.assertEqual(uncovered_handler_path_aliases(), [])

    def test_alias_scan_covers_first_if_branch_and_all_or_fallbacks(self):
        blocks = _dispatch_tool_blocks()
        self.assertGreaterEqual(len(blocks), 50)
        self.assertEqual(blocks[0][0], "plate_health")
        aliases_by_tool = discover_handler_or_arg_aliases()
        scanned_tools = {tool for tool, _left, _right in aliases_by_tool}
        for tool_name, source in blocks:
            if not _OR_ALIAS_PATTERN.search(source):
                continue
            self.assertIn(
                tool_name,
                scanned_tools,
                msg=f"{tool_name} has args.get-or-args.get fallback but was not scanned",
            )
        self.assertTrue(
            any(left == "fragment_path" and right == "fragment" for _t, left, right in aliases_by_tool),
            "expected fragment_path/fragment pair from attach_fragment branch",
        )

    def _escape_values(self) -> list[object]:
        outside = self.repo_root.parent / "mcp-escape-outside"
        outside.mkdir(exist_ok=True)
        return [
            "../",
            str(outside),
            "/etc/passwd",
        ]

    def test_every_path_param_rejects_escape(self):
        rows = all_registered_path_parameters()
        for tool_name, param in rows:
            for escape in self._escape_values():
                with self.subTest(tool=tool_name, param=param, escape=escape):
                    args = self._sample_args(tool_name, param, escape)
                    with self.assertRaises(PathConfinementError):
                        confine_tool_arguments(tool_name, args, self.repo_root)

    def test_symlink_escape_rejected_for_path_params(self):
        with tempfile.TemporaryDirectory(dir=self.repo_root) as tmp:
            link = Path(tmp) / "link-out"
            outside = self.repo_root.parent / "mcp-symlink-outside"
            outside.mkdir(exist_ok=True)
            try:
                link.symlink_to(outside, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"symlink unsupported: {exc}")
            for tool_name, param in all_registered_path_parameters()[:15]:
                with self.subTest(tool=tool_name, param=param):
                    args = self._sample_args(tool_name, param, str(link))
                    with self.assertRaises(PathConfinementError):
                        confine_tool_arguments(tool_name, args, self.repo_root)

    def _sample_args(self, tool_name: str, param: str, value: object) -> dict:
        if param in ("paths", "artifact_paths"):
            return {param: [value]}
        if param == "target" and tool_name in (
            "plate_collab_ownership_claim",
            "plate_collab_ownership_release",
        ):
            return {"kind": "path", param: value}
        if tool_name == "plate_feature_media_attach_fragment":
            args = {"record_id": "r1", "fragment_path": "."}
            args[param] = value
            return args
        if tool_name == "plate_self_migrate_merge_markers":
            return {"repo_root": ".", param: value}
        return {param: value}


if __name__ == "__main__":
    unittest.main()