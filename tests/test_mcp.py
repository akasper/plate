import json
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from plate_core import __version__
from plate_core.bootstrap import BootstrapAction, BootstrapReport
from plate_core.epics import EpicStatusReport, EpicSummary
from plate_core.features import FeatureFlag, FeatureReport
from plate_core.health import HealthReport
from plate_core.mcp.tools import ValidateE2eTestsTool
from plate_core.mcp_server import _handle_tools_call, run
from plate_core.pr_babysit import BabysitReport


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
            goals_page_present=True,
            open_question_count=0,
            plate_config_present=False,
            plate_config_valid=False,
            curiosity_answers_present=False,
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

    @patch(
        "plate_core.mcp_server.sys.stdin",
        new_callable=lambda: io.StringIO('{"jsonrpc":"2.0","id":1,"method":"initialize"}\n'),
    )
    @patch("plate_core.mcp_server._write")
    def test_initialize_reports_package_version(self, mock_write, _mock_stdin):
        run()
        payload = mock_write.call_args[0][0]
        self.assertEqual(payload["result"]["serverInfo"]["name"], "plate-mcp")
        self.assertEqual(payload["result"]["serverInfo"]["version"], __version__)

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
        self.assertEqual(len(payload["agents"]), 15)
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
    def test_tools_call_plate_contexts(self, mock_write):
        _handle_tools_call(15, {"name": "plate_contexts", "arguments": {}})
        payload = json.loads(mock_write.call_args[0][0]["result"]["content"][0]["text"])
        self.assertGreaterEqual(len(payload["contexts"]), 6)
        self.assertEqual(payload["contexts"][0]["id"], "process")

    @patch("plate_core.mcp_server._write")
    def test_tools_call_plate_context(self, mock_write):
        _handle_tools_call(16, {"name": "plate_context", "arguments": {"context_id": "release-targeting"}})
        payload = json.loads(mock_write.call_args[0][0]["result"]["content"][0]["text"])
        self.assertEqual(payload["id"], "release-targeting")
        self.assertIn("gh plate release status", payload["machine_surfaces"])

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
    def test_tools_call_plate_config_get(self, mock_write):
        with tempfile.TemporaryDirectory() as tmp:
            _handle_tools_call(12, {"name": "plate_config_get", "arguments": {"repo_root": tmp}})
            payload = json.loads(mock_write.call_args[0][0]["result"]["content"][0]["text"])
            self.assertFalse(payload["present"])
            self.assertEqual(payload["source"], "defaults")

    @patch("plate_core.mcp_server._write")
    def test_tools_call_plate_config_init(self, mock_write):
        with tempfile.TemporaryDirectory() as tmp:
            _handle_tools_call(13, {"name": "plate_config_init", "arguments": {"repo_root": tmp}})
            payload = json.loads(mock_write.call_args[0][0]["result"]["content"][0]["text"])
            self.assertTrue(payload["present"])
            self.assertTrue((Path(tmp) / ".plate").exists())

    @patch("plate_core.mcp_server._write")
    def test_tools_call_plate_config_upgrade(self, mock_write):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / ".plate").write_text(
                json.dumps(
                    {
                        "version": "1.0",
                        "methodology": {"marker_prefix": "PLATES-CORE"},
                        "extensions": {"enabled": True},
                        "overrides": {},
                    }
                ),
                encoding="utf-8",
            )
            _handle_tools_call(14, {"name": "plate_config_upgrade", "arguments": {"repo_root": tmp}})
            payload = json.loads(mock_write.call_args[0][0]["result"]["content"][0]["text"])
            self.assertTrue(payload["changed"])
            self.assertEqual(payload["current_version"], "1.2")

    @patch("plate_core.mcp_server._write")
    def test_tools_call_plate_plan_epic(self, mock_write):
        _handle_tools_call(12, {"name": "plate_plan_epic", "arguments": {}})
        self.assertTrue(mock_write.called)
        result = mock_write.call_args[0][0]["result"]
        self.assertFalse(result["isError"])
        payload = json.loads(result["content"][0]["text"])
        self.assertEqual(payload["tool"], "plate_plan_epic")
        self.assertEqual(payload["status"], "stub")
        # CLI-agnostic verification per #206 / grok-build epic: note should not lock to specific TUI
        self.assertIn("CLI-agnostic", payload.get("note", ""))

    @patch("plate_core.mcp_server._write")
    @patch("plate_core.mcp_server.babysit_pr")
    def test_tools_call_plate_pr_babysit(self, mock_babysit_pr, mock_write):
        mock_babysit_pr.return_value = BabysitReport(
            repo="akasper/plate",
            pr_number=112,
            detected_threads=3,
            actionable_threads=2,
            trigger_comment_posted=False,
        )
        _handle_tools_call(
            13,
            {"name": "plate_pr_babysit", "arguments": {"repo": "akasper/plate", "pr_number": 112}},
        )
        payload = json.loads(mock_write.call_args[0][0]["result"]["content"][0]["text"])
        self.assertEqual(payload["pr_number"], 112)
        self.assertEqual(payload["actionable_threads"], 2)

    @patch("plate_core.mcp_server._write")
    @patch("plate_core.mcp_server.resolve_review_thread")
    def test_tools_call_plate_resolve_review_thread(self, mock_resolve_review_thread, mock_write):
        mock_resolve_review_thread.return_value = {"repo": "akasper/plate", "thread_id": "T1", "resolved": True}
        _handle_tools_call(
            14,
            {"name": "plate_resolve_review_thread", "arguments": {"repo": "akasper/plate", "thread_id": "T1"}},
        )
        payload = json.loads(mock_write.call_args[0][0]["result"]["content"][0]["text"])
        self.assertTrue(payload["resolved"])

    @patch("plate_core.mcp_server._write")
    @patch("plate_core.mcp_server.get_release_target_epic_guidance")
    def test_tools_call_plate_release_target_epic(self, mock_guidance, mock_write):
        mock_guidance.return_value = type(
            "Guidance",
            (),
            {
                "to_dict": lambda self: {
                    "repo": "akasper/plate",
                    "epic": {"number": 306},
                    "active_next_release": {"number": 50},
                    "can_target": True,
                    "api_write_supported": False,
                    "message": "manual step required",
                    "manual_steps": ["1. Do the UI link"],
                }
            },
        )()
        _handle_tools_call(
            15,
            {"name": "plate_release_target_epic", "arguments": {"repo": "akasper/plate", "epic_number": 306}},
        )
        payload = json.loads(mock_write.call_args[0][0]["result"]["content"][0]["text"])
        self.assertTrue(payload["can_target"])
        self.assertFalse(payload["api_write_supported"])

    @patch("plate_core.mcp_server._write")
    @patch("plate_core.mcp_server.cleanup_dead_branches")
    def test_tools_call_plate_release_cleanup_branches(self, mock_cleanup, mock_write):
        mock_cleanup.return_value = type(
            "CleanupReport",
            (),
            {
                "to_dict": lambda self: {
                    "repo": "akasper/plate",
                    "base_branch": "main",
                    "apply": False,
                    "scanned_branches": 4,
                    "candidates": ["feature-merged"],
                    "deleted": [],
                    "failed": [],
                    "skipped_open_pr": [],
                    "skipped_not_merged": [],
                    "warnings": [],
                }
            },
        )()
        _handle_tools_call(
            16,
            {"name": "plate_release_cleanup_branches", "arguments": {"repo": "akasper/plate"}},
        )
        payload = json.loads(mock_write.call_args[0][0]["result"]["content"][0]["text"])
        self.assertEqual(payload["repo"], "akasper/plate")
        self.assertEqual(payload["candidates"], ["feature-merged"])

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
        self.assertIn("plate_config_get", names)
        self.assertIn("plate_config_validate", names)
        self.assertIn("plate_config_init", names)
        self.assertIn("plate_config_upgrade", names)
        self.assertIn("plate_release_target_epic", names)
        self.assertIn("plate_release_cleanup_branches", names)

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

    @patch("plate_core.mcp_server._write")
    @patch(
        "plate_core.mcp_server.sys.stdin",
        new_callable=lambda: io.StringIO('{"jsonrpc":"2.0","id":7,"method":"tools/list"}\n'),
    )
    def test_tools_list_includes_plate_pr_babysit(self, _mock_stdin, mock_write):
        run()
        tools = mock_write.call_args[0][0]["result"]["tools"]
        names = {tool["name"] for tool in tools}
        self.assertIn("plate_pr_babysit", names)
        self.assertIn("plate_resolve_review_thread", names)

    @patch("plate_core.mcp_server._write")
    @patch(
        "plate_core.mcp_server.sys.stdin",
        new_callable=lambda: io.StringIO('{"jsonrpc":"2.0","id":20,"method":"tools/list"}\n'),
    )
    def test_tools_list_includes_curiosity_qanda_tools(self, _mock_stdin, mock_write):
        """Feature #154: Core MCP tools for Q&A/Curiosity are discoverable."""
        run()
        tools = mock_write.call_args[0][0]["result"]["tools"]
        names = {tool["name"] for tool in tools}
        for expected in [
            "plate_list_questions",
            "plate_get_question",
            "plate_record_answer",
            "plate_get_answers",
            "plate_synthesize_priorities",
            "plate_create_blocking_question",  # Feature #147 last-resort creation
        ]:
            self.assertIn(expected, names)

    @patch("plate_core.mcp_server._write")
    def test_tools_call_curiosity_list_questions_stub(self, mock_write):
        """Smoke test handler path for #154 tools (real GH calls mocked at higher level in integration)."""
        # The tool will attempt GhClient inside; we just ensure no crash in dispatch and error payload shape
        _handle_tools_call(21, {"name": "plate_list_questions", "arguments": {"repo": "akasper/nonexistent-for-test"}})
        self.assertTrue(mock_write.called)
        result = mock_write.call_args[0][0]["result"]
        # Either success content or isError=True with message (both acceptable for this smoke)
        self.assertIn("content", result)

    @patch("plate_core.mcp_server._write")
    @patch("plate_core.mcp_server.get_health")
    def test_tools_call_plate_what_next(self, mock_get_health, mock_write):
        """Feature #285: plate_what_next MCP tool is registered and callable (v1 static)."""
        mock_get_health.return_value = HealthReport(
            plate_config_present=True,
            repo="akasper/plate_core",
            label_coverage_ok=True,
            missing_labels=[],
            binary_artifacts_tracked=0,
            branch_protection_enabled=True,
            open_epic_count=0,
            status="pass",
        )
        _handle_tools_call(30, {"name": "plate_what_next", "arguments": {"repo": "akasper/plate_core"}})
        self.assertTrue(mock_write.called)
        result = mock_write.call_args[0][0]["result"]
        self.assertIn("content", result)

    def test_create_blocking_question_tool_exists_and_schema(self):
        """Feature #147/#151: Blocking creation tool is registered (Epic #139)."""
        from plate_core.mcp.curiosity_tools import CreateBlockingQuestionTool, CURIOSITY_TOOLS
        self.assertIn("plate_create_blocking_question", CURIOSITY_TOOLS)
        # Basic instantiation / method presence (full integration tested via MCP dispatch + GH in higher suites)
        tool = CreateBlockingQuestionTool
        self.assertTrue(hasattr(tool, "execute"))

    @patch("plate_core.mcp_server._write")
    def test_tools_call_create_blocking_stub(self, mock_write):
        """Smoke for #147 tool dispatch (real creation mocked at GH layer)."""
        _handle_tools_call(22, {
            "name": "plate_create_blocking_question",
            "arguments": {
                "original_issue_number": 999,
                "blockage_point": "Missing clarity on scope",
                "missing_info": "Confirm primary user persona",
                "repo": "akasper/nonexistent-for-test"
            }
        })
        self.assertTrue(mock_write.called)

    def test_validate_e2e_tests_tool_status_and_actionable(self):
        """#263: ValidateE2eTestsTool produces clear pass/warn/fail + next_steps (stricter, CI/evidence aware)."""
        # Non-existent -> fail
        res = ValidateE2eTestsTool.execute("/non/existent/path/12345")
        self.assertEqual(res["status"], "fail")
        self.assertFalse(res["valid"])
        self.assertIn("Repository not found", res["issues"][0])
        self.assertTrue(any("next_steps" in k or "next" in str(v).lower() for k, v in res.items() if isinstance(v, (list, str))))

        # Empty temp dir -> fail (missing core)
        with tempfile.TemporaryDirectory() as tmp:
            res = ValidateE2eTestsTool.execute(tmp)
            self.assertIn(res["status"], ("fail", "warn"))
            self.assertIn("Missing playwright.config.ts", " ".join(res["issues"]))
            self.assertTrue(res.get("next_steps"))
            # Has actionable recs
            self.assertTrue(any("init-playwright" in r or "Copy" in r for r in res.get("recommendations", [])))

        # Minimal good structure -> should reach warn or pass (no critical missing)
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / "playwright.config.ts").touch()
            (p / "tests" / "e2e" / "specs").mkdir(parents=True)
            (p / "tests" / "e2e" / "specs" / "example.spec.ts").touch()
            (p / "package.json").write_text('{"devDependencies": {"@playwright/test": "^1"}, "scripts": {"test:e2e": "playwright test"}}')
            (p / ".github" / "workflows").mkdir(parents=True)
            (p / ".github" / "workflows" / "test.yml").write_text("playwright: npx playwright test")
            res = ValidateE2eTestsTool.execute(tmp)
            self.assertIn(res["status"], ("pass", "warn"))
            self.assertTrue(res.get("next_steps"))
            # Evidence rec if no gifs yet (acceptable)
            recs = " ".join(res.get("recommendations", []))
            self.assertTrue("evidence" in recs.lower() or "GIF" in recs or "record" in recs.lower() or not recs)

    @patch("plate_core.mcp.tools.subprocess.run")
    def test_record_e2e_gif_tool_trimming_and_size_advice(self, mock_run):
        """#263: RecordE2eGifTool accepts trim params, returns size/quality/recommendations, advises trim for large GIFs."""
        from plate_core.mcp.tools import RecordE2eGifTool
        # Success with GIF present (mock)
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / "scripts").mkdir(parents=True)
            (p / "scripts" / "e2e-record.sh").touch()
            gif_dir = p / "tests" / "e2e" / "fixtures" / "gifs"
            gif_dir.mkdir(parents=True)
            gif = gif_dir / "demo.gif"
            gif.write_bytes(b"0" * (6 * 1024 * 1024))  # >5MB to trigger advice
            mock_run.return_value = type("R", (), {"returncode": 0, "stderr": ""})()
            res = RecordE2eGifTool.execute(tmp, "demo", quality="low", start="00:00:02", duration=10)
            self.assertEqual(res["status"], "success")
            self.assertEqual(res["quality"], "low")
            self.assertIn("gif_path", res)
            self.assertTrue(res.get("recommendations"))
            self.assertIn("trim", res)  # trim params echoed
            recs_str = " ".join(res.get("recommendations", []))
            self.assertTrue("large" in recs_str.lower() or "trim" in recs_str.lower())

        # Error on bad test name
        res = RecordE2eGifTool.execute(".", "bad name with spaces!")
        self.assertEqual(res["status"], "error")
        self.assertIn("Invalid test name", res["message"])

if __name__ == "__main__":
    unittest.main()
