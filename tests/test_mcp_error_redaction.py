"""JSON-RPC tools/call errors must not leak absolute host paths (#1475)."""
from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import patch

from plate_core.mcp.path_confinement import redact_absolute_paths, session_repo_root
from plate_core.mcp.tool_profiles import PROFILE_ALL, configure_mcp_tool_profiles, reset_mcp_tool_profile_session
from plate_core.mcp_server import _handle_tools_call


class McpErrorRedactionTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["PLATE_MCP_TOOL_PROFILES"] = PROFILE_ALL
        reset_mcp_tool_profile_session()
        configure_mcp_tool_profiles(PROFILE_ALL)

    def tearDown(self) -> None:
        os.environ.pop("PLATE_MCP_TOOL_PROFILES", None)
        reset_mcp_tool_profile_session()

    @patch("plate_core.mcp_server._write")
    def test_path_escape_error_has_no_absolute_paths(self, mock_write):
        root = session_repo_root()
        outside = str(root.parent / "mcp-rpc-escape-outside")
        _handle_tools_call(
            42,
            {
                "name": "plate_import_payload",
                "arguments": {"target_dir": outside},
            },
        )
        payload = mock_write.call_args[0][0]
        text = payload["result"]["content"][0]["text"]
        self.assertTrue(payload["result"]["isError"])
        self.assertNotIn(str(root), text)
        self.assertNotIn(outside, text)
        self.assertIn("repository root", text.lower())

    def test_redact_home_and_tilde_paths(self):
        home = Path.home()
        raw = f"open failed: {home}/secrets and ~/other/file"
        redacted = redact_absolute_paths(raw)
        self.assertNotIn(str(home), redacted)
        self.assertNotIn("~/other", redacted)
        self.assertIn("<home>", redacted)

    @patch("plate_core.mcp_server._execute_mcp_tool")
    @patch("plate_core.mcp_server._write")
    def test_non_confinement_error_redacts_paths(self, mock_write, mock_exec):
        home = Path.home()
        secret = str(home / "mcp-leak-test" / "x")
        mock_exec.side_effect = RuntimeError(f"read failed: {secret}")
        _handle_tools_call(7, {"name": "plate_get_health", "arguments": {}})
        payload = mock_write.call_args[0][0]
        text = payload["result"]["content"][0]["text"]
        self.assertTrue(payload["result"]["isError"])
        self.assertNotIn(secret, text)
        self.assertNotIn(str(home), text)


if __name__ == "__main__":
    unittest.main()