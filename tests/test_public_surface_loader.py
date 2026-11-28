"""Unit tests for ``plate_core.public_surface_loader`` (#1546)."""

from __future__ import annotations

import argparse
import ast
import unittest
from unittest import mock

from plate_core.public_surface_loader import (
    _mcp_tool_definitions_via_literal_eval,
    load_cli_tree,
    load_mcp_tool_definitions,
)


class PublicSurfaceLoaderTests(unittest.TestCase):
    def test_load_cli_tree_exposes_top_level_commands(self) -> None:
        root = load_cli_tree()
        choices = None
        for action in root._actions:
            if isinstance(action, argparse._SubParsersAction):
                choices = action.choices
                break
        self.assertIsNotNone(choices)
        assert choices is not None
        self.assertIn("health", choices)

    def test_load_mcp_tool_definitions_returns_named_tools(self) -> None:
        tools = load_mcp_tool_definitions()
        self.assertGreater(len(tools), 0)
        names = {t["name"] for t in tools if isinstance(t, dict) and t.get("name")}
        self.assertIn("plate_health", names)
        for entry in tools:
            self.assertIn("name", entry)
            self.assertIn("inputSchema", entry)

    def test_load_mcp_prefers_import_when_available(self) -> None:
        sentinel = [{"name": "plate_import_probe", "inputSchema": {"type": "object"}}]
        with mock.patch(
            "plate_core.public_surface_loader._mcp_tool_definitions_via_import",
            return_value=sentinel,
        ):
            self.assertIs(load_mcp_tool_definitions(), sentinel)

    def test_load_mcp_falls_back_to_literal_eval(self) -> None:
        with mock.patch(
            "plate_core.public_surface_loader._mcp_tool_definitions_via_import",
            return_value=None,
        ):
            tools = load_mcp_tool_definitions()
        self.assertGreater(len(tools), 0)

    def test_literal_eval_raises_when_all_tools_missing(self) -> None:
        with mock.patch(
            "plate_core.public_surface_loader._MCP_SERVER_PATH",
        ) as path_mock:
            path_mock.read_text.return_value = "x = 1\n"
            with self.assertRaises(RuntimeError):
                _mcp_tool_definitions_via_literal_eval()

    def test_no_exec_in_loader_source(self) -> None:
        import plate_core.public_surface_loader as mod
        from pathlib import Path

        source = Path(mod.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                self.assertNotEqual(node.func.id, "exec")


if __name__ == "__main__":
    unittest.main()