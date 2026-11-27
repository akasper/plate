"""MCP tool registry consistency and dispatch coverage (#1475)."""
from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

from plate_core.mcp.registry import (
    assert_registry_consistency,
    build_tool_registry,
    dispatchable_tool_names,
    execute_tool,
    listed_tool_names,
)
from plate_core.mcp.tool_profiles import PROFILE_ALL, reset_mcp_tool_profile_session
import plate_core.mcp_server  # noqa: F401 — registers tool executor
from plate_core.mcp_server import _execute_mcp_tool


class McpRegistryConsistencyTests(unittest.TestCase):
    def test_listed_equals_registry_keys(self):
        registry = build_tool_registry()
        self.assertEqual(listed_tool_names(), frozenset(registry.keys()))

    def test_assert_registry_consistency(self):
        assert_registry_consistency()


class McpRegistryDispatchTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["PLATE_MCP_TOOL_PROFILES"] = PROFILE_ALL
        reset_mcp_tool_profile_session()

    def tearDown(self) -> None:
        os.environ.pop("PLATE_MCP_TOOL_PROFILES", None)
        reset_mcp_tool_profile_session()

    def test_every_dispatchable_tool_is_dispatchable(self):
        """Dispatch must not raise KeyError (Unknown tool) for every advertised name."""
        minimal: dict[str, dict] = {
            "plate_agent": {"agent_id": "research-agent"},
            "plate_skill": {"skill_id": "crud-projects"},
            "plate_context": {"context_id": "process"},
            "plate_get_discussion": {"number": 1},
            "plate_list_discussion_comments": {"number": 1},
            "plate_add_discussion_comment": {"number": 1, "body": "hi"},
            "plate_create_discussion": {"title": "t", "body": "b"},
            "plate_pr_verify": {"pr_number": 1},
            "record_e2e_gif": {"repo_path": ".", "test_name": "login"},
            "plate_perform_test_coverage_audit": {"dry_run": True},
        }

        @patch("plate_core.github_client.GhClient")
        @patch("plate_core.mcp_server.get_health")
        @patch("plate_core.discussions.list_discussions", return_value=[])
        @patch(
            "plate_core.mcp.audit_tools.PerformInformationAuditTool.execute",
            return_value={"count": 0, "proposed_questions": []},
        )
        def _exercise(
            _info_mock,
            _disc_mock,
            mock_health,
            _gh_mock,
            *,
            tool_name: str,
        ) -> None:
            from plate_core.health import HealthReport

            mock_health.return_value = HealthReport(
                repo="owner/repo",
                label_coverage_ok=True,
                missing_labels=[],
                binary_artifacts_tracked=0,
                branch_protection_enabled=True,
                open_epic_count=0,
                status="pass",
                goals_page_present=True,
                open_question_count=0,
                plate_config_present=False,
                plate_config_valid=False,
                curiosity_answers_present=False,
            )
            args = minimal.get(tool_name, {})
            try:
                _execute_mcp_tool(tool_name, args)
            except KeyError as exc:
                if str(exc).startswith("Unknown tool"):
                    self.fail(str(exc))
            except Exception:
                pass  # missing required args / mocked I/O is acceptable

        for name in sorted(dispatchable_tool_names()):
            with self.subTest(tool=name):
                _exercise(tool_name=name)

    def test_execute_tool_uses_registered_executor(self):
        with patch("plate_core.mcp_server.get_health") as mock_health:
            from plate_core.health import HealthReport

            mock_health.return_value = HealthReport(
                repo="owner/repo",
                label_coverage_ok=True,
                missing_labels=[],
                binary_artifacts_tracked=0,
                branch_protection_enabled=True,
                open_epic_count=0,
                status="pass",
                goals_page_present=True,
                open_question_count=0,
                plate_config_present=False,
                plate_config_valid=False,
                curiosity_answers_present=False,
            )
            out = execute_tool("plate_health", {"repo": "owner/repo"})
            payload = json.loads(json.dumps(out, default=str))
            self.assertEqual(payload["repo"], "owner/repo")


class McpReleaseMediaProfileTests(unittest.TestCase):
    def test_release_media_tools_map_to_release_media_profile(self):
        from plate_core.mcp.tool_profiles import profiles_for_tool

        for name in listed_tool_names():
            if name.startswith("plate_release_media_"):
                self.assertIn("release_media", profiles_for_tool(name))


if __name__ == "__main__":
    unittest.main()