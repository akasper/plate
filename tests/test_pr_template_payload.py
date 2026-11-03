"""#1049: slim PR template payload, bootstrap seed, and repo parity."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from plate_core.bootstrap import (
    PULL_REQUEST_TEMPLATE_REL,
    _maybe_queue_bootstrap_pull_request_template,
    _remote_repo_path_missing,
)
from plate_core.github_client import GhApiError
from plate_core.import_payload import import_payload
from plate_core.template_payload import payload_root


def _repo_template_path() -> Path:
    root = Path(__file__).resolve().parent.parent
    return root / ".github" / "PULL_REQUEST_TEMPLATE.md"


def _payload_template_path() -> Path:
    return payload_root() / ".github" / "PULL_REQUEST_TEMPLATE.md"


class PullRequestTemplateContentTests(unittest.TestCase):
    REQUIRED_SECTIONS = (
        "## Summary",
        "## What changed",
        "## How verified",
        "## Links",
        "## Visual evidence",
    )

    def test_repo_and_payload_copies_match(self):
        repo_text = _repo_template_path().read_text(encoding="utf-8")
        payload_text = _payload_template_path().read_text(encoding="utf-8")
        self.assertEqual(repo_text, payload_text)

    def test_slim_structure_and_required_notes(self):
        text = _repo_template_path().read_text(encoding="utf-8")
        for heading in self.REQUIRED_SECTIONS:
            self.assertIn(heading, text, msg=f"missing section {heading}")
        self.assertNotIn("\n|", text, "tables must not appear in the slim template")
        self.assertIn("Closes #N", text)
        self.assertIn("apply exactly one pr type label", text.lower())
        self.assertIn(".agentic/releases/", text)
        self.assertIn("--attach", text)
        self.assertIn("Visual evidence: not applicable —", text)
        self.assertIn("Do not commit images", text)
        self.assertIn("320px", text)


class PullRequestTemplateImportTests(unittest.TestCase):
    def test_import_safe_creates_template_when_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dest = root / PULL_REQUEST_TEMPLATE_REL
            self.assertFalse(dest.is_file())
            report = import_payload(root, strategy="safe", apply=True)
            self.assertTrue(report["ok"])
            self.assertIn(PULL_REQUEST_TEMPLATE_REL, report["created"])
            self.assertTrue(dest.is_file())
            self.assertIn("## Visual evidence", dest.read_text(encoding="utf-8"))


class PullRequestTemplateBootstrapQueueTests(unittest.TestCase):
    def test_queue_when_remote_missing_and_not_already_pending(self):
        client = Mock()
        pending: list[tuple[str, bytes]] = []
        template_root = payload_root()
        queued = _maybe_queue_bootstrap_pull_request_template(
            "owner/repo",
            client,
            None,
            pending,
            template_root,
            platform="posix",
        )
        self.assertTrue(queued)
        self.assertEqual([rel for rel, _ in pending], [PULL_REQUEST_TEMPLATE_REL])
        text = pending[0][1].decode("utf-8")
        self.assertIn("## Summary", text)

    def test_skip_when_already_queued(self):
        client = Mock()
        pending: list[tuple[str, bytes]] = [(PULL_REQUEST_TEMPLATE_REL, b"# existing\n")]
        template_root = payload_root()
        queued = _maybe_queue_bootstrap_pull_request_template(
            "owner/repo",
            client,
            None,
            pending,
            template_root,
            platform="posix",
        )
        self.assertFalse(queued)
        self.assertEqual(len(pending), 1)

    def test_remote_repo_path_missing_for_pr_template(self):
        client = Mock()

        def api_side(endpoint, *a, **k):
            if PULL_REQUEST_TEMPLATE_REL in endpoint:
                raise GhApiError("HTTP 404: Not Found")
            return {"type": "file"}

        client.api.side_effect = api_side
        self.assertTrue(
            _remote_repo_path_missing("owner/repo", client, PULL_REQUEST_TEMPLATE_REL, "abc123")
        )
