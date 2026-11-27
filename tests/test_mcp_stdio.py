"""MCP stdio loop robustness (#1475)."""
from __future__ import annotations

import io
import json
import unittest
from unittest.mock import patch

from plate_core.mcp_server import run


class McpStdioLoopTests(unittest.TestCase):
    def test_invalid_json_returns_parse_error(self):
        line = "not-json\n"
        written: list[dict] = []

        def capture(obj: dict) -> None:
            written.append(obj)

        with patch("plate_core.mcp_server.sys.stdin", io.StringIO(line)), patch(
            "plate_core.mcp_server._write", side_effect=capture
        ):
            run()
        self.assertEqual(written[0]["error"]["code"], -32700)

    def test_ping_method(self):
        line = json.dumps({"jsonrpc": "2.0", "id": 9, "method": "ping"}) + "\n"
        written: list[dict] = []

        def capture(obj: dict) -> None:
            written.append(obj)

        with patch("plate_core.mcp_server.sys.stdin", io.StringIO(line)), patch(
            "plate_core.mcp_server._write", side_effect=capture
        ):
            run()
        self.assertEqual(written[0]["id"], 9)
        self.assertIn("result", written[0])

    def test_bad_json_then_valid_initialize(self):
        stdin = io.StringIO(
            "oops\n"
            + json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
            + "\n"
        )
        written: list[dict] = []

        def capture(obj: dict) -> None:
            written.append(obj)

        with patch("plate_core.mcp_server.sys.stdin", stdin), patch(
            "plate_core.mcp_server._write", side_effect=capture
        ):
            run()
        self.assertEqual(written[0]["error"]["code"], -32700)
        self.assertEqual(written[1]["result"]["serverInfo"]["name"], "plate-mcp")


if __name__ == "__main__":
    unittest.main()