"""
Tests for single-agent delegation support across CLI, MCP, and plugin surfaces (Issue #83).

TDD approach: these tests are written first and define the contract for:
- DelegationResult dataclass with required fields
- build_delegation_prompt() deterministic prompt generation
- delegate_to_agent() catalog lookup + prompt assembly
- CLI: gh plate agents delegate <id> --task "..." [--json]
- MCP: plate_delegate_to_agent tool
- MCP: tools/list includes plate_delegate_to_agent
- plate agent .agent.md references delegation workflow

All tests are written before the implementation so that failures drive development.
"""
from __future__ import annotations

import io
import json
import re
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from plate_core.cli import main
from plate_core.mcp_server import _handle_tools_call, run


_REPO_ROOT = Path(__file__).resolve().parent.parent


class DelegationResultStructureTests(unittest.TestCase):
    """DelegationResult dataclass must have the contract fields defined in the design doc."""

    def setUp(self):
        from plate_core.baseline_catalog import load_baseline_catalog
        load_baseline_catalog.cache_clear()

    def tearDown(self):
        from plate_core.baseline_catalog import load_baseline_catalog
        load_baseline_catalog.cache_clear()

    def test_delegate_to_agent_returns_delegation_result(self):
        from plate_core.baseline_catalog import delegate_to_agent, DelegationResult
        result = delegate_to_agent("project-manager", "Plan the next sprint")
        self.assertIsInstance(result, DelegationResult)

    def test_delegation_result_has_required_fields(self):
        from plate_core.baseline_catalog import delegate_to_agent
        result = delegate_to_agent("research-agent", "Summarize MCP frameworks in Python")
        d = result.to_dict()
        for field in (
            "agent_id", "agent_name", "agent_description",
            "task_description", "delegation_prompt",
            "relevant_skills", "surfaces", "invocation_hints",
        ):
            self.assertIn(field, d, f"DelegationResult.to_dict() missing field '{field}'")

    def test_delegation_result_agent_id_matches_request(self):
        from plate_core.baseline_catalog import delegate_to_agent
        result = delegate_to_agent("designer", "Create wireframes for onboarding")
        self.assertEqual(result.agent_id, "designer")

    def test_delegation_result_task_description_preserved(self):
        from plate_core.baseline_catalog import delegate_to_agent
        task = "Research competitor pricing for a new SaaS product"
        result = delegate_to_agent("market-researcher", task)
        self.assertEqual(result.task_description, task)

    def test_delegation_result_invocation_hints_has_three_surfaces(self):
        from plate_core.baseline_catalog import delegate_to_agent
        result = delegate_to_agent("project-manager", "Plan the epic")
        hints = result.invocation_hints
        for key in ("copilot_plugin", "gh_plate", "mcp"):
            self.assertIn(key, hints, f"invocation_hints missing key '{key}'")
            self.assertTrue(hints[key], f"invocation_hints['{key}'] must not be empty")

    def test_delegation_result_relevant_skills_non_empty(self):
        from plate_core.baseline_catalog import delegate_to_agent
        result = delegate_to_agent("project-manager", "Groom the backlog")
        self.assertGreater(len(result.relevant_skills), 0)

    def test_delegation_result_surfaces_includes_all_three(self):
        from plate_core.baseline_catalog import delegate_to_agent
        result = delegate_to_agent("project-manager", "Plan release")
        self.assertIn("copilot-plugin", result.surfaces)
        self.assertIn("gh-plate", result.surfaces)
        self.assertIn("mcp", result.surfaces)

    def test_delegate_to_agent_unknown_id_raises(self):
        from plate_core.baseline_catalog import delegate_to_agent, BaselineCatalogError
        with self.assertRaises(BaselineCatalogError):
            delegate_to_agent("nonexistent-agent", "Do something")


class DelegationPromptTests(unittest.TestCase):
    """build_delegation_prompt() must produce a deterministic, well-structured prompt."""

    def setUp(self):
        from plate_core.baseline_catalog import load_baseline_catalog
        load_baseline_catalog.cache_clear()

    def tearDown(self):
        from plate_core.baseline_catalog import load_baseline_catalog
        load_baseline_catalog.cache_clear()

    def test_build_delegation_prompt_contains_agent_name(self):
        from plate_core.baseline_catalog import build_delegation_prompt, get_agent, list_skills
        agent = get_agent("research-agent")
        skills = [s for s in list_skills() if s.id in agent.primary_skill_ids]
        prompt = build_delegation_prompt(agent, "Research MCP frameworks", skills)
        self.assertIn(agent.name, prompt)

    def test_build_delegation_prompt_contains_task(self):
        from plate_core.baseline_catalog import build_delegation_prompt, get_agent, list_skills
        agent = get_agent("project-manager")
        skills = [s for s in list_skills() if s.id in agent.primary_skill_ids]
        task = "Plan the Q3 release cycle"
        prompt = build_delegation_prompt(agent, task, skills)
        self.assertIn(task, prompt)

    def test_build_delegation_prompt_contains_at_least_one_skill(self):
        from plate_core.baseline_catalog import build_delegation_prompt, get_agent, list_skills
        agent = get_agent("project-manager")
        skills = [s for s in list_skills() if s.id in agent.primary_skill_ids]
        prompt = build_delegation_prompt(agent, "Define next epic", skills)
        # At least one skill name should appear in the prompt
        skill_names_in_prompt = [s.name for s in skills if s.name in prompt]
        self.assertGreater(len(skill_names_in_prompt), 0, "Prompt must reference at least one skill name")

    def test_build_delegation_prompt_non_empty_for_all_agents(self):
        from plate_core.baseline_catalog import build_delegation_prompt, list_agents, list_skills
        agents = list_agents()
        skills_by_id = {s.id: s for s in list_skills()}
        for agent in agents:
            skills = [skills_by_id[sid] for sid in agent.primary_skill_ids if sid in skills_by_id]
            prompt = build_delegation_prompt(agent, "Test task", skills)
            self.assertTrue(prompt.strip(), f"Empty delegation prompt for agent '{agent.id}'")

    def test_delegation_prompt_in_result_contains_task(self):
        from plate_core.baseline_catalog import delegate_to_agent
        task = "Design a new onboarding flow"
        result = delegate_to_agent("designer", task)
        self.assertIn(task, result.delegation_prompt)


class CliDelegationTests(unittest.TestCase):
    """gh plate agents delegate <id> --task "..." [--json] must work correctly."""

    def setUp(self):
        from plate_core.baseline_catalog import load_baseline_catalog
        load_baseline_catalog.cache_clear()

    def tearDown(self):
        from plate_core.baseline_catalog import load_baseline_catalog
        load_baseline_catalog.cache_clear()

    def test_agents_delegate_json_returns_delegation_result(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(["agents", "delegate", "project-manager", "--task", "Plan the sprint", "--json"])
        self.assertEqual(code, 0, "CLI delegation must return exit code 0")
        payload = json.loads(out.getvalue().strip())
        self.assertEqual(payload["agent_id"], "project-manager")
        self.assertIn("delegation_prompt", payload)
        self.assertIn("invocation_hints", payload)

    def test_agents_delegate_json_all_required_fields(self):
        out = io.StringIO()
        with redirect_stdout(out):
            main(["agents", "delegate", "research-agent", "--task", "Research MCP frameworks", "--json"])
        payload = json.loads(out.getvalue().strip())
        for field in ("agent_id", "agent_name", "task_description", "delegation_prompt",
                      "relevant_skills", "surfaces", "invocation_hints"):
            self.assertIn(field, payload, f"CLI delegate JSON missing field '{field}'")

    def test_agents_delegate_unknown_id_returns_error_exit_code(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(["agents", "delegate", "does-not-exist", "--task", "something", "--json"])
        self.assertNotEqual(code, 0, "Unknown agent id must return non-zero exit code")

    def test_agents_delegate_human_readable_output_mentions_agent(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(["agents", "delegate", "designer", "--task", "Create wireframes"])
        self.assertEqual(code, 0)
        output = out.getvalue()
        self.assertIn("Designer", output)

    def test_agents_delegate_task_preserved_in_json(self):
        task = "Define the release strategy for v2"
        out = io.StringIO()
        with redirect_stdout(out):
            main(["agents", "delegate", "project-manager", "--task", task, "--json"])
        payload = json.loads(out.getvalue().strip())
        self.assertEqual(payload["task_description"], task)


class McpDelegationTests(unittest.TestCase):
    """plate_delegate_to_agent MCP tool must return correct delegation payload."""

    def setUp(self):
        from plate_core.baseline_catalog import load_baseline_catalog
        load_baseline_catalog.cache_clear()

    def tearDown(self):
        from plate_core.baseline_catalog import load_baseline_catalog
        load_baseline_catalog.cache_clear()

    @patch("plate_core.mcp_server._write")
    def test_mcp_delegate_to_agent_returns_result(self, mock_write):
        _handle_tools_call(20, {
            "name": "plate_delegate_to_agent",
            "arguments": {"agent_id": "research-agent", "task_description": "Summarize MCP frameworks"}
        })
        self.assertTrue(mock_write.called)
        result = mock_write.call_args[0][0]["result"]
        self.assertFalse(result["isError"])
        payload = json.loads(result["content"][0]["text"])
        self.assertEqual(payload["agent_id"], "research-agent")
        self.assertIn("delegation_prompt", payload)

    @patch("plate_core.mcp_server._write")
    def test_mcp_delegate_unknown_agent_returns_error(self, mock_write):
        _handle_tools_call(21, {
            "name": "plate_delegate_to_agent",
            "arguments": {"agent_id": "no-such-agent", "task_description": "Do something"}
        })
        result = mock_write.call_args[0][0]["result"]
        self.assertTrue(result["isError"])

    @patch("plate_core.mcp_server._write")
    def test_mcp_delegate_missing_agent_id_returns_error(self, mock_write):
        _handle_tools_call(22, {
            "name": "plate_delegate_to_agent",
            "arguments": {"task_description": "Do something"}
        })
        result = mock_write.call_args[0][0]["result"]
        self.assertTrue(result["isError"])

    @patch("plate_core.mcp_server._write")
    def test_mcp_delegate_all_required_fields_in_response(self, mock_write):
        _handle_tools_call(23, {
            "name": "plate_delegate_to_agent",
            "arguments": {"agent_id": "designer", "task_description": "Create UI mockups"}
        })
        payload = json.loads(mock_write.call_args[0][0]["result"]["content"][0]["text"])
        for field in ("agent_id", "agent_name", "task_description", "delegation_prompt",
                      "relevant_skills", "surfaces", "invocation_hints"):
            self.assertIn(field, payload, f"MCP delegation response missing field '{field}'")


class McpToolsListDelegationTests(unittest.TestCase):
    """tools/list must include plate_delegate_to_agent with correct schema."""

    def _get_tools_list(self) -> list[dict]:
        line = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}) + "\n"
        written: list[dict] = []

        def _capture(obj: dict) -> None:
            written.append(obj)

        with patch("plate_core.mcp_server.sys.stdin", io.StringIO(line)):
            with patch("plate_core.mcp_server._write", side_effect=_capture):
                run()

        return written[0]["result"]["tools"]

    def test_tools_list_includes_plate_delegate_to_agent(self):
        tools = self._get_tools_list()
        names = {t["name"] for t in tools}
        self.assertIn("plate_delegate_to_agent", names)

    def test_plate_delegate_to_agent_has_description(self):
        tools = self._get_tools_list()
        tool = next((t for t in tools if t["name"] == "plate_delegate_to_agent"), None)
        self.assertIsNotNone(tool, "plate_delegate_to_agent not in tools/list")
        self.assertTrue(tool.get("description"), "plate_delegate_to_agent must have a description")

    def test_plate_delegate_to_agent_schema_declares_agent_id(self):
        tools = self._get_tools_list()
        tool = next((t for t in tools if t["name"] == "plate_delegate_to_agent"), None)
        schema = tool.get("inputSchema", {})
        self.assertIn("agent_id", schema.get("properties", {}))

    def test_plate_delegate_to_agent_schema_declares_task_description(self):
        tools = self._get_tools_list()
        tool = next((t for t in tools if t["name"] == "plate_delegate_to_agent"), None)
        schema = tool.get("inputSchema", {})
        self.assertIn("task_description", schema.get("properties", {}))


class PluginAgentDelegationTests(unittest.TestCase):
    """plugin/agents/plate.agent.md must reference the delegation workflow."""

    def _read_plate_agent(self) -> str:
        path = _REPO_ROOT / "plugin" / "agents" / "plate.agent.md"
        self.assertTrue(path.exists(), "plugin/agents/plate.agent.md not found")
        return path.read_text(encoding="utf-8")

    def test_plate_agent_references_delegation_tool(self):
        content = self._read_plate_agent()
        self.assertIn(
            "plate_delegate_to_agent", content,
            "plate.agent.md must reference the plate_delegate_to_agent MCP tool"
        )

    def test_plate_agent_instructions_mention_delegation(self):
        content = self._read_plate_agent()
        delegation_terms = ["delegate", "delegation"]
        found = any(term in content.lower() for term in delegation_terms)
        self.assertTrue(
            found,
            "plate.agent.md instructions must mention delegation workflow"
        )


if __name__ == "__main__":
    unittest.main()
