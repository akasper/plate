import io
import json
import os
import unittest
from unittest.mock import patch

from plate_core.mcp.tool_profiles import (
    ENV_TOOL_PROFILES,
    PROFILE_ALL,
    PROFILE_DEFAULT,
    configure_mcp_tool_profiles,
    expand_profile_names,
    filter_tool_definitions,
    parse_tool_profile_spec,
    profiles_for_tool,
    reset_mcp_tool_profile_session,
    tool_visible,
)
from plate_core.mcp_server import run


class McpToolProfileMappingTests(unittest.TestCase):
    def test_every_listed_tool_has_profiles(self):
        import re
        from pathlib import Path

        text = Path("src/plate_core/mcp_server.py").read_text()
        names: list[str] = []
        in_list = False
        for line in text.splitlines():
            if 'elif method == "tools/list":' in line:
                in_list = True
                continue
            if in_list and "visible_tools" in line:
                break
            if in_list:
                m = re.search(r'"name": "([^"]+)"', line)
                if m:
                    names.append(m.group(1))
        self.assertGreaterEqual(len(names), 180)
        for name in names:
            with self.subTest(name=name):
                self.assertTrue(profiles_for_tool(name))

    def test_default_alias_expands_core_profiles(self):
        expanded = expand_profile_names([PROFILE_DEFAULT])
        self.assertIn("review", expanded)
        self.assertIn("delegation", expanded)
        self.assertNotIn(PROFILE_ALL, expanded)


class McpToolProfileSessionTests(unittest.TestCase):
    def tearDown(self) -> None:
        reset_mcp_tool_profile_session()
        os.environ.pop(ENV_TOOL_PROFILES, None)

    def _tools_list(self, *, env: str | None = None, argv: list[str] | None = None) -> list[dict]:
        if env is not None:
            os.environ[ENV_TOOL_PROFILES] = env
        reset_mcp_tool_profile_session()
        line = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}) + "\n"
        written: list[dict] = []

        def _capture(obj: dict) -> None:
            written.append(obj)

        stdin_patch = patch("plate_core.mcp_server.sys.stdin", io.StringIO(line))
        write_patch = patch("plate_core.mcp_server._write", side_effect=_capture)
        if argv is not None:
            with stdin_patch, write_patch, patch("plate_core.mcp_server.sys.argv", argv):
                run()
        else:
            with stdin_patch, write_patch:
                run()
        return written[0]["result"]["tools"]

    def test_default_profile_is_lean(self):
        tools = self._tools_list(env=PROFILE_DEFAULT)
        names = {t["name"] for t in tools}
        self.assertIn("plate_delegate_to_agent", names)
        self.assertIn("plate_pr_babysit", names)
        self.assertNotIn("plate_bootstrap", names)
        self.assertGreaterEqual(len(tools), 18)
        self.assertLessEqual(len(tools), 35)

    def test_all_profile_lists_every_tool(self):
        default_tools = self._tools_list(env=PROFILE_DEFAULT)
        all_tools = self._tools_list(env=PROFILE_ALL)
        self.assertGreater(len(all_tools), len(default_tools))
        self.assertGreaterEqual(len(all_tools), 180)

    def test_argv_overrides_env(self):
        tools = self._tools_list(
            env=PROFILE_DEFAULT,
            argv=["plate-mcp", "--tool-profiles", PROFILE_ALL],
        )
        self.assertGreaterEqual(len(tools), 180)

    def test_filter_respects_profile_membership(self):
        active = parse_tool_profile_spec("delegation")
        sample = [
            {"name": "plate_delegate_to_agent", "description": "x", "inputSchema": {}},
            {"name": "plate_bootstrap", "description": "y", "inputSchema": {}},
        ]
        filtered = filter_tool_definitions(sample, active)
        self.assertEqual([t["name"] for t in filtered], ["plate_delegate_to_agent"])
        self.assertTrue(tool_visible("plate_task_create", expand_profile_names(["task"])))


if __name__ == "__main__":
    unittest.main()
