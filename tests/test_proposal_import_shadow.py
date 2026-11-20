"""Regression tests for proposal import shadowing (Issue #1497).

``cli`` and ``mcp_server`` import ``decide_proposal``/``list_proposals`` from
``.design_research_approval`` and also (under distinct aliases) from
``.monitoring``. Previously the monitoring import shadowed the artifact
functions, so artifact call sites crashed with ``TypeError``.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from plate_core import cli, design_research_approval, mcp_server, monitoring
from plate_core.mcp_server import _handle_tools_call


class ProposalImportShadowTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._approvals_dir = Path(self._tmp.name) / "approvals"
        self._monitor_dir = Path(self._tmp.name) / "monitoring"
        self._patches = [
            patch.object(design_research_approval, "APPROVALS_DIR", self._approvals_dir),
            patch.object(monitoring, "MONITOR_DIR", self._monitor_dir),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in self._patches:
            p.stop()
        self._tmp.cleanup()

    def test_cli_artifact_names_resolve_to_design_research_approval(self):
        self.assertIs(cli.list_proposals, design_research_approval.list_proposals)
        self.assertIs(cli.decide_proposal, design_research_approval.decide_proposal)

    def test_cli_monitor_names_resolve_to_monitoring(self):
        self.assertIs(cli.list_monitor_proposals, monitoring.list_proposals)
        self.assertIs(cli.decide_monitor_proposal, monitoring.decide_proposal)

    def test_mcp_artifact_names_resolve_to_design_research_approval(self):
        self.assertIs(mcp_server.list_proposals, design_research_approval.list_proposals)
        self.assertIs(mcp_server.decide_proposal, design_research_approval.decide_proposal)

    def test_mcp_monitor_names_resolve_to_monitoring(self):
        self.assertIs(mcp_server.list_monitor_proposals, monitoring.list_proposals)
        self.assertIs(mcp_server.decide_monitor_proposal, monitoring.decide_proposal)

    @patch("plate_core.mcp_server.assert_tool_allowed")
    @patch("plate_core.mcp_server._write")
    def test_mcp_artifact_list_dispatches_without_error(self, mock_write, _mock_allowed):
        _handle_tools_call(
            1, {"name": "plate_artifact_list", "arguments": {}}
        )
        result = mock_write.call_args[0][0]["result"]
        self.assertFalse(result["isError"])
        payload = json.loads(result["content"][0]["text"])
        self.assertIsInstance(payload["proposals"], list)

    @patch("plate_core.mcp_server.assert_tool_allowed")
    @patch("plate_core.mcp_server._write")
    def test_mcp_monitor_list_dispatches_without_error(self, mock_write, _mock_allowed):
        _handle_tools_call(
            2, {"name": "plate_monitor_list", "arguments": {}}
        )
        result = mock_write.call_args[0][0]["result"]
        self.assertFalse(result["isError"])
        payload = json.loads(result["content"][0]["text"])
        self.assertIsInstance(payload["proposals"], list)


if __name__ == "__main__":
    unittest.main()
