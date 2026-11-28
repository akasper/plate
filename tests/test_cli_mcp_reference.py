import importlib
import subprocess
import unittest
from pathlib import Path
from unittest import mock


class CliMcpReferenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]

    def test_legacy_inline_tool_definitions_via_ast(self) -> None:
        from plate_core.cli_mcp_reference import (
            _legacy_inline_tool_definitions,
            load_all_mcp_tool_definitions,
        )
        from plate_core.mcp.tool_profiles import list_mcp_tool_names

        legacy = _legacy_inline_tool_definitions(self.repo_root)
        self.assertEqual({t["name"] for t in legacy}, set(list_mcp_tool_names()))
        loaded = load_all_mcp_tool_definitions(self.repo_root)
        self.assertEqual(len(legacy), len(loaded))

    def test_load_all_mcp_tool_definitions_uses_ast_fallback_when_registry_missing(self) -> None:
        from plate_core.cli_mcp_reference import load_all_mcp_tool_definitions
        from plate_core.mcp.tool_profiles import list_mcp_tool_names

        real_import = importlib.__import__

        def import_hook(name, globals=None, locals=None, fromlist=(), level=0):
            if name in ("plate_core.mcp.registry", "plate_core.mcp.tool_definitions"):
                raise ImportError(f"blocked import for test: {name}")
            return real_import(name, globals, locals, fromlist, level)

        with mock.patch("builtins.__import__", side_effect=import_hook):
            tools = load_all_mcp_tool_definitions(self.repo_root)
        self.assertEqual({t["name"] for t in tools}, set(list_mcp_tool_names()))

    def test_stable_mcp_parameters_match_authoritative_input_schemas(self) -> None:
        from plate_core.cli_mcp_reference import (
            collect_stable_mcp_tools,
            load_all_mcp_tool_definitions,
            parameters_from_input_schema,
        )

        by_name = {tool["name"]: tool for tool in load_all_mcp_tool_definitions(self.repo_root)}
        for ref in collect_stable_mcp_tools(self.repo_root):
            schema = by_name[ref.name].get("inputSchema") or {}
            expected = tuple(parameters_from_input_schema(schema))
            self.assertEqual(ref.parameters, expected, msg=ref.name)

    def test_rendered_reference_lists_stable_counts(self) -> None:
        from plate_core.cli_mcp_reference import (
            collect_stable_cli_commands,
            collect_stable_mcp_tools,
            load_stable_surface_keys,
        )

        stable_cli, stable_mcp = load_stable_surface_keys(self.repo_root)
        cli_cmds = collect_stable_cli_commands(self.repo_root)
        mcp_tools = collect_stable_mcp_tools(self.repo_root)
        self.assertEqual(len(cli_cmds), len(stable_cli))
        self.assertEqual(len(mcp_tools), len(stable_mcp))
        content = (self.repo_root / "docs/cli-mcp-reference.md").read_text(encoding="utf-8")
        self.assertIn(f"**{len(cli_cmds)}** leaf invocations", content)
        self.assertIn(f"**{len(mcp_tools)}** tools from the stable profiles", content)

    def test_cli_mcp_reference_in_sync(self) -> None:
        from plate_core.cli_mcp_reference import cli_mcp_reference_in_sync

        ok, errors = cli_mcp_reference_in_sync(self.repo_root)
        self.assertTrue(ok, msg="\n".join(errors))

    def test_generate_script_check_passes_in_repo(self) -> None:
        result = subprocess.run(
            ["python3", str(self.repo_root / "scripts" / "generate-cli-mcp-reference.py"), "--check"],
            capture_output=True,
            text=True,
            cwd=self.repo_root,
            env={"PYTHONPATH": str(self.repo_root / "src"), **dict(__import__("os").environ)},
        )
        self.assertEqual(result.returncode, 0, msg=f"{result.stderr}\n{result.stdout}")
        self.assertIn("CLI/MCP reference OK", result.stdout)

    def test_cli_mcp_reference_in_sync_detects_drift(self) -> None:
        from plate_core.cli_mcp_reference import cli_mcp_reference_in_sync

        path = self.repo_root / "docs/cli-mcp-reference.md"
        original = path.read_text(encoding="utf-8")
        try:
            path.write_text(original + "\n# stale\n", encoding="utf-8")
            ok, errors = cli_mcp_reference_in_sync(self.repo_root)
            self.assertFalse(ok)
            self.assertTrue(errors)
        finally:
            path.write_text(original, encoding="utf-8")


if __name__ == "__main__":
    unittest.main()