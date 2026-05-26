import json
import unittest
from unittest.mock import patch

from plate_core.health import HealthReport
from plate_core.mcp_server import _handle_tools_call


class McpTests(unittest.TestCase):
    @patch("plate_core.mcp_server._write")
    @patch("plate_core.mcp_server.get_health")
    def test_tools_call_plate_health(self, mock_get_health, mock_write):
        mock_get_health.return_value = HealthReport(
            repo="akasper/plate_core",
            label_coverage_ok=True,
            missing_labels=[],
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


if __name__ == "__main__":
    unittest.main()

