import json
import io
import unittest
from unittest.mock import patch

from plate_core.bootstrap import BootstrapAction, BootstrapReport
from plate_core.epics import EpicStatusReport, EpicSummary
from plate_core.features import FeatureFlag, FeatureReport
from plate_core.health import HealthReport
from plate_core.mcp_server import _handle_tools_call, run


class McpTests(unittest.TestCase):
    @patch("plate_core.mcp_server._write")
    @patch("plate_core.mcp_server.get_health")
    def test_tools_call_plate_health(self, mock_get_health, mock_write):
        mock_get_health.return_value = HealthReport(
            repo="akasper/plate_core",
            label_coverage_ok=True,
            missing_labels=[],
            binary_artifacts_tracked=0,
            branch_protection_enabled=True,
            open_epic_count=1,
            status="pass",
        )
        _handle_tools_call(1, {"name": "plate_health", "arguments": {"repo": "akasper/plate_core"}})
        self.assertTrue(mock_write.called)
        result = mock_write.call_args[0][0]["result"]
        content_text = result["content"][0]["text"]
        payload = json.loads(content_text)
        self.assertEqual(payload["repo"], "akasper/plate_core")
        self.assertEqual(payload["status"], "pass")

    @patch("plate_core.mcp_server._write")
    @patch("plate_core.mcp_server.get_health")
    def test_tools_call_returns_error_payload_when_health_raises(self, mock_get_health, mock_write):
        mock_get_health.side_effect = RuntimeError("boom")
        _handle_tools_call(7, {"name": "plate_health", "arguments": {"repo": "bad/repo"}})
        result = mock_write.call_args[0][0]["result"]
        self.assertTrue(result["isError"])
        self.assertIn("boom", result["content"][0]["text"])

    @patch("plate_core.mcp_server._write")
    @patch("plate_core.mcp_server.sys.stdin", new_callable=lambda: io.StringIO('{"jsonrpc":"2.0","method":"notifications/roots/list_changed"}\n'))
    def test_run_ignores_notification_without_id(self, _mock_stdin, mock_write):
        run()
        mock_write.assert_not_called()

    @patch("plate_core.mcp_server._write")
    @patch("plate_core.mcp_server.get_epic_status")
    def test_tools_call_plate_epic_status(self, mock_get_epic_status, mock_write):
        mock_get_epic_status.return_value = EpicStatusReport(
            repo="akasper/plate_core",
            open_epic_count=1,
            epics=[
                EpicSummary(
                    epic_label="Epic: plate-core-v1",
                    epic_issue_number=4,
                    epic_issue_title="v1",
                    epic_issue_state="open",
                    open_child_issues=5,
                    closed_child_issues=3,
                )
            ],
        )
        _handle_tools_call(9, {"name": "plate_epic_status", "arguments": {"repo": "akasper/plate_core"}})
        payload = json.loads(mock_write.call_args[0][0]["result"]["content"][0]["text"])
        self.assertEqual(payload["open_epic_count"], 1)
        self.assertEqual(payload["epics"][0]["epic_label"], "Epic: plate-core-v1")

    @patch("plate_core.mcp_server._write")
    def test_tools_call_plate_agents(self, mock_write):
        _handle_tools_call(11, {"name": "plate_agents", "arguments": {}})
        payload = json.loads(mock_write.call_args[0][0]["result"]["content"][0]["text"])
        self.assertEqual(len(payload["agents"]), 12)
        self.assertEqual(payload["agents"][0]["id"], "project-manager")

    @patch("plate_core.mcp_server._write")
    def test_tools_call_plate_agent(self, mock_write):
        _handle_tools_call(12, {"name": "plate_agent", "arguments": {"agent_id": "research-agent"}})
        payload = json.loads(mock_write.call_args[0][0]["result"]["content"][0]["text"])
        self.assertEqual(payload["id"], "research-agent")
        self.assertIn("research-synthesis", payload["primary_skill_ids"])

    @patch("plate_core.mcp_server._write")
    def test_tools_call_plate_skills(self, mock_write):
        _handle_tools_call(13, {"name": "plate_skills", "arguments": {}})
        payload = json.loads(mock_write.call_args[0][0]["result"]["content"][0]["text"])
        self.assertGreaterEqual(len(payload["skills"]), 18)

    @patch("plate_core.mcp_server._write")
    def test_tools_call_plate_skill(self, mock_write):
        _handle_tools_call(14, {"name": "plate_skill", "arguments": {"skill_id": "crud-projects"}})
        payload = json.loads(mock_write.call_args[0][0]["result"]["content"][0]["text"])
        self.assertEqual(payload["id"], "crud-projects")

    @patch("plate_core.mcp_server._write")
    @patch("plate_core.mcp_server.get_features")
    def test_tools_call_plate_features(self, mock_get_features, mock_write):
        mock_get_features.return_value = FeatureReport(
            repo="akasper/plate_core",
            features=[FeatureFlag(name="autonomous-mode", enabled=False, evidence=".github/AUTONOMOUS_MODE")],
        )
        _handle_tools_call(10, {"name": "plate_features", "arguments": {"repo": "akasper/plate_core"}})
        payload = json.loads(mock_write.call_args[0][0]["result"]["content"][0]["text"])
        self.assertEqual(payload["repo"], "akasper/plate_core")
        self.assertEqual(payload["features"][0]["name"], "autonomous-mode")

    @patch("plate_core.mcp_server._write")
    @patch("plate_core.mcp_server.run_bootstrap")
    def test_tools_call_plate_bootstrap(self, mock_run_bootstrap, mock_write):
        mock_run_bootstrap.return_value = BootstrapReport(
            repo="akasper/plate_core",
            apply_mode=False,
            actions=[BootstrapAction(name="enable-wiki", state="planned", detail="Set has_wiki=true")],
        )
        _handle_tools_call(11, {"name": "plate_bootstrap", "arguments": {"repo": "akasper/plate_core"}})
        payload = json.loads(mock_write.call_args[0][0]["result"]["content"][0]["text"])
        self.assertEqual(payload["repo"], "akasper/plate_core")
        self.assertEqual(payload["actions"][0]["name"], "enable-wiki")

    @patch("plate_core.mcp_server._write")
    def test_tools_call_plate_plan_epic(self, mock_write):
        _handle_tools_call(12, {"name": "plate_plan_epic", "arguments": {}})
        self.assertTrue(mock_write.called)
        result = mock_write.call_args[0][0]["result"]
        self.assertFalse(result["isError"])
        payload = json.loads(result["content"][0]["text"])
        self.assertEqual(payload["tool"], "plate_plan_epic")
        self.assertEqual(payload["status"], "stub")

    @patch("plate_core.mcp_server._write")
    @patch(
        "plate_core.mcp_server.sys.stdin",
        new_callable=lambda: io.StringIO('{"jsonrpc":"2.0","id":5,"method":"tools/list"}\n'),
    )
    def test_tools_list_includes_features_and_bootstrap(self, _mock_stdin, mock_write):
        run()
        tools = mock_write.call_args[0][0]["result"]["tools"]
        names = {tool["name"] for tool in tools}
        self.assertIn("plate_features", names)
        self.assertIn("plate_bootstrap", names)

    @patch("plate_core.mcp_server._write")
    @patch(
        "plate_core.mcp_server.sys.stdin",
        new_callable=lambda: io.StringIO('{"jsonrpc":"2.0","id":6,"method":"tools/list"}\n'),
    )
    def test_tools_list_includes_plan_epic(self, _mock_stdin, mock_write):
        run()
        tools = mock_write.call_args[0][0]["result"]["tools"]
        names = {tool["name"] for tool in tools}
        self.assertIn("plate_plan_epic", names)

if __name__ == "__main__":
    unittest.main()
