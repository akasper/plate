"""Tests for Task issue creation (#359)."""

from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from plate_core.tasks import (
    TASK_CLOSED_MARKER,
    build_task_body,
    close_task_with_signal,
    create_task,
    redact_sensitive,
)


class TestTaskBody(unittest.TestCase):
    def test_build_includes_required_sections(self):
        body = build_task_body(
            human_action="Create PyPI account",
            why_agent_cannot="Requires human identity on external system",
            context="Blocks publish workflow #625",
            instructions="1. Open pypi.org\n2. Enable trusted publisher",
            related_links=["#625", "https://pypi.org"],
            epic_milestone="Human Action Items",
        )
        self.assertIn("## Human action required", body)
        self.assertIn("## Why the agent cannot safely proceed", body)
        self.assertIn("## Context and affected artifacts", body)
        self.assertIn("## Best-effort instructions / next steps", body)
        self.assertIn("## Done signal", body)
        self.assertIn("## Related links", body)
        self.assertIn(TASK_CLOSED_MARKER, body)
        self.assertIn("Create PyPI account", body)
        self.assertIn("Human Action Items", body)

    def test_redact_secrets(self):
        raw = "token ghp_abcdefghijklmnopqrstuvwxyz012345 and password=hunter2"
        out = redact_sensitive(raw)
        self.assertNotIn("ghp_", out)
        self.assertIn("[REDACTED]", out)

    def test_create_task_dry_run(self):
        out = create_task(
            "Configure trusted publisher",
            human_action="Set up OIDC on PyPI",
            why_agent_cannot="External account ownership",
            context="#625",
            instructions="Use GitHub → PyPI trusted publisher UI",
            dry_run=True,
            client=Mock(),
            repo="owner/repo",
        )
        self.assertTrue(out["ok"])
        self.assertTrue(out["dry_run"])
        self.assertIn("Task", out["labels"])
        self.assertEqual(out["labels"].count("Task"), 1)
        self.assertTrue(out["title"].startswith("[Task]:"))
        self.assertIn("Human action required", out["body"])

    def test_create_task_posts_issue(self):
        client = Mock()
        client.api.return_value = {
            "number": 99,
            "html_url": "https://github.com/owner/repo/issues/99",
        }
        with patch("plate_core.tasks.resolve_repo", return_value="owner/repo"):
            out = create_task(
                "Do thing",
                human_action="Click approve",
                why_agent_cannot="Needs human",
                context="ctx",
                instructions="steps",
                dry_run=False,
                client=client,
                repo="owner/repo",
            )
        self.assertTrue(out["ok"])
        self.assertEqual(out["number"], 99)
        client.api.assert_called()
        args, kwargs = client.api.call_args
        self.assertEqual(args[0], "repos/owner/repo/issues")
        self.assertEqual(kwargs.get("method"), "POST")
        fields = kwargs.get("fields") or {}
        self.assertIn("Task", fields.get("labels") or [])
        self.assertNotIn("Feature", fields.get("labels") or [])

    def test_close_task_adds_marker(self):
        client = Mock()
        client.api.return_value = {}
        with patch("plate_core.tasks.resolve_repo", return_value="owner/repo"):
            out = close_task_with_signal(5, comment="Done", client=client, repo="owner/repo")
        self.assertTrue(out["ok"])
        # first call is comment
        cargs = client.api.call_args_list[0]
        self.assertIn("comments", cargs[0][0])
        self.assertIn(TASK_CLOSED_MARKER, cargs[1]["fields"]["body"])


if __name__ == "__main__":
    unittest.main()
