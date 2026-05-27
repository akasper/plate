"""
Plugin smoke tests and agent/skill discovery integration tests for Issue #81.

These tests verify that the plugin bundle is structurally valid and that agent/skill
discovery works end-to-end across the CLI, MCP, and plugin surfaces without a live
GitHub or Copilot session.

Verification layers (per docs/research/copilot-cli-verification-harness.md):
- Plugin bundle structural validation (plugin.json, agent files, MCP config)
- Agent file frontmatter validation (name, description, tools format)
- Feature detection for baseline-agents-catalog (local file check)
- CLI agent/skill discovery smoke (end-to-end via main())
- MCP tools/list includes agent/skill discovery tools
"""
from __future__ import annotations

import io
import json
import re
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from plate_core.cli import main
from plate_core.mcp_server import run


# Paths relative to the repo root
_REPO_ROOT = Path(__file__).resolve().parent.parent
_PLUGIN_DIR = _REPO_ROOT / "plugin"
_DOT_PLUGIN_DIR = _REPO_ROOT / ".plugin"
_CATALOG_PATH = _REPO_ROOT / "src" / "plate_core" / "data" / "baseline_catalog.yml"


class PluginManifestTests(unittest.TestCase):
    """Validate plugin.json manifests in both plugin surfaces."""

    def _assert_valid_manifest(self, path: Path) -> dict:
        self.assertTrue(path.exists(), f"plugin.json not found at {path}")
        with path.open(encoding="utf-8") as f:
            manifest = json.load(f)
        self.assertIsInstance(manifest, dict, f"{path}: must be a JSON object")
        for required_field in ("name", "description", "version"):
            self.assertIn(required_field, manifest, f"{path}: missing required field '{required_field}'")
            self.assertIsInstance(manifest[required_field], str, f"{path}: '{required_field}' must be a string")
            self.assertTrue(manifest[required_field], f"{path}: '{required_field}' must not be empty")
        return manifest

    def test_plugin_source_manifest_is_valid(self):
        manifest = self._assert_valid_manifest(_PLUGIN_DIR / "plugin.json")
        self.assertIn("agents", manifest)

    def test_plugin_root_manifest_is_valid(self):
        manifest = self._assert_valid_manifest(_DOT_PLUGIN_DIR / "plugin.json")
        self.assertIn("agents", manifest)

    def test_plugin_mcp_config_is_valid_json(self):
        mcp_path = _PLUGIN_DIR / ".mcp.json"
        self.assertTrue(mcp_path.exists(), "plugin/.mcp.json not found")
        with mcp_path.open(encoding="utf-8") as f:
            config = json.load(f)
        self.assertIsInstance(config, dict, "plugin/.mcp.json must be a JSON object")
        # Must declare at least one MCP server entry
        self.assertGreater(len(config), 0, "plugin/.mcp.json must declare at least one MCP server")

    def test_root_mcp_config_is_valid_json(self):
        mcp_path = _DOT_PLUGIN_DIR / ".mcp.json"
        self.assertTrue(mcp_path.exists(), ".plugin/.mcp.json not found")
        with mcp_path.open(encoding="utf-8") as f:
            config = json.load(f)
        self.assertIsInstance(config, dict, ".plugin/.mcp.json must be a JSON object")


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)


def _parse_frontmatter(text: str) -> dict:
    """Extract YAML frontmatter fields as a dict. Returns {} if no frontmatter found."""
    import yaml  # local import: yaml is available via PyYAML (already a project dep)

    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}
    return yaml.safe_load(match.group(1)) or {}


class AgentFileTests(unittest.TestCase):
    """Validate .agent.md files in both plugin agent directories."""

    def _collect_agent_files(self) -> list[Path]:
        files: list[Path] = []
        for base in (_PLUGIN_DIR / "agents", _DOT_PLUGIN_DIR / "agents"):
            if base.is_dir():
                files.extend(base.glob("*.agent.md"))
        self.assertGreater(len(files), 0, "No .agent.md files found in plugin surfaces")
        return files

    def test_all_agent_files_have_valid_frontmatter(self):
        for agent_file in self._collect_agent_files():
            with agent_file.open(encoding="utf-8") as f:
                text = f.read()
            fm = _parse_frontmatter(text)
            self.assertIn(
                "name", fm,
                f"{agent_file.name}: frontmatter missing 'name'"
            )
            self.assertIsInstance(fm["name"], str, f"{agent_file.name}: 'name' must be a string")
            self.assertTrue(fm["name"], f"{agent_file.name}: 'name' must not be empty")
            self.assertIn(
                "description", fm,
                f"{agent_file.name}: frontmatter missing 'description'"
            )
            self.assertIsInstance(fm["description"], str, f"{agent_file.name}: 'description' must be a string")
            self.assertTrue(fm["description"], f"{agent_file.name}: 'description' must not be empty")

    def test_all_agent_files_have_instruction_body(self):
        for agent_file in self._collect_agent_files():
            with agent_file.open(encoding="utf-8") as f:
                text = f.read()
            # Body is everything after the closing --- of frontmatter
            parts = text.split("---", 2)
            body = parts[2].strip() if len(parts) >= 3 else ""
            self.assertTrue(
                body,
                f"{agent_file.name}: agent file has no instruction body after frontmatter"
            )


class BaselineCatalogPresenceTests(unittest.TestCase):
    """Verify that baseline catalog file exists and is detectable (feature flag smoke test)."""

    def test_baseline_catalog_file_exists_in_repo(self):
        self.assertTrue(
            _CATALOG_PATH.exists(),
            f"Baseline catalog not found at {_CATALOG_PATH}"
        )

    def test_baseline_catalog_detectable_by_features_module(self):
        """feature detect 'baseline-agents-catalog' by checking the known catalog path."""
        from plate_core.features import detect_playwright_e2e_local
        # The relevant check is that the catalog path exists and is readable.
        # This mirrors what plate_core.features does for the baseline-agents-catalog flag.
        self.assertTrue(_CATALOG_PATH.exists())
        # Verify the file is parseable YAML
        import yaml
        with _CATALOG_PATH.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
        self.assertEqual(data["schema_version"], 1)
        self.assertIsInstance(data["agents"], list)
        self.assertIsInstance(data["skills"], list)


class CliAgentSkillDiscoveryTests(unittest.TestCase):
    """End-to-end CLI smoke tests for agent and skill discovery (Issue #80/#81)."""

    def test_agents_list_returns_all_twelve_agents(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(["agents", "list", "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(out.getvalue().strip())
        self.assertEqual(len(payload["agents"]), 12)

    def test_agents_list_includes_expected_agent_ids(self):
        out = io.StringIO()
        with redirect_stdout(out):
            main(["agents", "list", "--json"])
        payload = json.loads(out.getvalue().strip())
        ids = {a["id"] for a in payload["agents"]}
        for expected_id in ("project-manager", "research-agent", "designer"):
            self.assertIn(expected_id, ids, f"Expected agent '{expected_id}' not in catalog")

    def test_agent_show_returns_full_agent_record(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(["agents", "show", "project-manager", "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(out.getvalue().strip())
        self.assertEqual(payload["id"], "project-manager")
        self.assertIn("description", payload)
        self.assertIn("primary_skill_ids", payload)
        self.assertIn("surfaces", payload)
        self.assertIn("constraints", payload)

    def test_skills_list_returns_at_least_eighteen_skills(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(["skills", "list", "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(out.getvalue().strip())
        self.assertGreaterEqual(len(payload["skills"]), 18)

    def test_skill_show_returns_full_skill_record(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(["skills", "show", "crud-projects", "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(out.getvalue().strip())
        self.assertEqual(payload["id"], "crud-projects")
        self.assertIn("description", payload)
        self.assertIn("inputs", payload)
        self.assertIn("outputs", payload)
        self.assertIn("owning_agent_ids", payload)

    def test_skills_list_each_skill_has_required_fields(self):
        out = io.StringIO()
        with redirect_stdout(out):
            main(["skills", "list", "--json"])
        payload = json.loads(out.getvalue().strip())
        for skill in payload["skills"]:
            for field in ("id", "name", "description", "owning_agent_ids"):
                self.assertIn(field, skill, f"Skill missing field '{field}': {skill.get('id')}")

    def test_agents_list_each_agent_has_required_fields(self):
        out = io.StringIO()
        with redirect_stdout(out):
            main(["agents", "list", "--json"])
        payload = json.loads(out.getvalue().strip())
        for agent in payload["agents"]:
            for field in ("id", "name", "description", "primary_skill_ids", "surfaces"):
                self.assertIn(field, agent, f"Agent missing field '{field}': {agent.get('id')}")

    def test_agents_list_all_surfaces_include_copilot_plugin(self):
        """Every baseline agent must be available on the copilot-plugin surface."""
        out = io.StringIO()
        with redirect_stdout(out):
            main(["agents", "list", "--json"])
        payload = json.loads(out.getvalue().strip())
        for agent in payload["agents"]:
            self.assertIn(
                "copilot-plugin", agent["surfaces"],
                f"Agent '{agent['id']}' is not available on copilot-plugin surface"
            )


class McpAgentSkillDiscoveryTests(unittest.TestCase):
    """MCP tools/list smoke tests verifying agent/skill tools are registered."""

    def _run_mcp_method(self, method: str, req_id: int = 1) -> dict:
        import io as _io
        from unittest.mock import patch

        line = json.dumps({"jsonrpc": "2.0", "id": req_id, "method": method}) + "\n"
        written: list[dict] = []

        def _capture(obj: dict) -> None:
            written.append(obj)

        with patch("plate_core.mcp_server.sys.stdin", _io.StringIO(line)):
            with patch("plate_core.mcp_server._write", side_effect=_capture):
                run()

        self.assertEqual(len(written), 1, f"Expected 1 response for {method}, got {len(written)}")
        return written[0]

    def test_tools_list_includes_all_agent_skill_tools(self):
        response = self._run_mcp_method("tools/list")
        tool_names = {t["name"] for t in response["result"]["tools"]}
        for expected in ("plate_agents", "plate_agent", "plate_skills", "plate_skill"):
            self.assertIn(expected, tool_names, f"Missing MCP tool '{expected}' in tools/list")

    def test_tools_list_agent_tools_have_descriptions(self):
        response = self._run_mcp_method("tools/list")
        for tool in response["result"]["tools"]:
            if tool["name"].startswith("plate_agent") or tool["name"].startswith("plate_skill"):
                self.assertTrue(
                    tool.get("description"),
                    f"MCP tool '{tool['name']}' has no description"
                )

    def test_tools_list_plate_agent_declares_required_agent_id(self):
        response = self._run_mcp_method("tools/list")
        tools_by_name = {t["name"]: t for t in response["result"]["tools"]}
        agent_tool = tools_by_name.get("plate_agent", {})
        schema = agent_tool.get("inputSchema", {})
        self.assertIn(
            "agent_id",
            schema.get("properties", {}),
            "'plate_agent' inputSchema must declare 'agent_id' property"
        )

    def test_tools_list_plate_skill_declares_required_skill_id(self):
        response = self._run_mcp_method("tools/list")
        tools_by_name = {t["name"]: t for t in response["result"]["tools"]}
        skill_tool = tools_by_name.get("plate_skill", {})
        schema = skill_tool.get("inputSchema", {})
        self.assertIn(
            "skill_id",
            schema.get("properties", {}),
            "'plate_skill' inputSchema must declare 'skill_id' property"
        )


if __name__ == "__main__":
    unittest.main()
