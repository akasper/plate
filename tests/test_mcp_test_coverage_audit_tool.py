"""Tests for plate_perform_test_coverage_audit MCP tool."""
from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

from plate_core.mcp.tool_profiles import (
    ENV_TOOL_PROFILES,
    PROFILE_ALL,
    configure_mcp_tool_profiles,
    reset_mcp_tool_profile_session,
)
from plate_core.mcp_server import _handle_tools_call


class McpTestCoverageAuditTests(unittest.TestCase):
    """plate_perform_test_coverage_audit MCP tool must not raise NameError."""

    def setUp(self) -> None:
        os.environ[ENV_TOOL_PROFILES] = PROFILE_ALL
        reset_mcp_tool_profile_session()
        configure_mcp_tool_profiles(PROFILE_ALL)

    def tearDown(self) -> None:
        os.environ.pop(ENV_TOOL_PROFILES, None)
        reset_mcp_tool_profile_session()

    @patch("plate_core.mcp_server._write")
    def test_call_returns_result_without_error(self, mock_write):
        _handle_tools_call(1, {
            "name": "plate_perform_test_coverage_audit",
            "arguments": {"dry_run": True},
        })
        self.assertTrue(mock_write.called)
        result = mock_write.call_args[0][0].get("result")
        self.assertIsNotNone(result, "Response must contain a 'result' key")
        self.assertFalse(result["isError"])
        json.loads(result["content"][0]["text"])

    @patch("plate_core.mcp_server._write")
    @patch("plate_core.mcp.audit_tools.PerformTestCoverageAuditTool.execute")
    def test_passes_repo_and_dry_run_to_execute(self, mock_execute, mock_write):
        mock_execute.return_value = {"ok": True}
        _handle_tools_call(2, {
            "name": "plate_perform_test_coverage_audit",
            "arguments": {"repo": "owner/name", "dry_run": True},
        })
        mock_execute.assert_called_once_with(repo="owner/name", dry_run=True)