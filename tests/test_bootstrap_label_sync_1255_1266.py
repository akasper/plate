"""Bootstrap label registry sync and seeded issue labels (#1255, #1256, #1266)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from plate_core.bootstrap import run_bootstrap
from plate_core.github_client import GhApiError
from plate_core.github_labels import sync_repository_labels_from_registry
from plate_core.health import HealthReport

_TEMPLATE_LABELS = (
    Path(__file__).resolve().parent.parent
    / "src/plate_core/template_payload/.github/labels.yml"
)


def _write_template_tree(root: Path, *, include_labels: bool) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "AGENTS.md").write_text("# AGENTS\n", encoding="utf-8")
    (root / "README.md").write_text("# README\n", encoding="utf-8")
    goals = root / "docs/wiki"
    goals.mkdir(parents=True)
    (goals / "Goals.md").write_text("# Goals\n", encoding="utf-8")
    if include_labels and _TEMPLATE_LABELS.is_file():
        dest = root / ".github"
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "labels.yml").write_text(_TEMPLATE_LABELS.read_text(encoding="utf-8"), encoding="utf-8")


class GithubLabelSyncTests(unittest.TestCase):
    def test_sync_empty_repo_creates_all_registry_labels(self):
        registry = Path(tempfile.mkdtemp()) / "labels.yml"
        registry.write_text(
            """
- name: Bug
  color: d73a4a
  description: Issue or PR type: defect.
- name: Feature
  color: 0e8a16
  description: Issue or PR type: feature.
""".strip()
            + "\n",
            encoding="utf-8",
        )
        client = Mock()

        def api_side(endpoint, *a, **k):
            if endpoint.endswith("/labels?per_page=100&page=1"):
                return []
            if endpoint.endswith("/labels") and k.get("method") == "POST":
                return {}
            raise AssertionError(f"unexpected api call: {endpoint} {k}")

        client.api.side_effect = api_side
        outcomes = sync_repository_labels_from_registry(
            client, "owner/repo", registry, apply=True
        )
        self.assertEqual(len(outcomes), 2)
        self.assertTrue(all(o.state == "applied" for o in outcomes))
        posts = [c for c in client.api.call_args_list if c.kwargs.get("method") == "POST"]
        self.assertEqual(len(posts), 2)
        names = {c.kwargs["fields"]["name"] for c in posts}
        self.assertEqual(names, {"Bug", "Feature"})

    def test_sync_renames_github_default_case_collisions(self):
        registry = Path(tempfile.mkdtemp()) / "labels.yml"
        registry.write_text(
            """
- name: Bug
  color: d73a4a
  description: Issue or PR type: defect.
- name: Documentation
  color: "0075ca"
  description: PR type: documentation-only change.
- name: Question
  color: d4c5f9
  description: Issue type: information goal.
""".strip()
            + "\n",
            encoding="utf-8",
        )
        client = Mock()

        def api_side(endpoint, *a, **k):
            if endpoint.endswith("/labels?per_page=100&page=1"):
                return [
                    {"name": "bug", "color": "d73a4a", "description": "old"},
                    {"name": "documentation", "color": "0075ca", "description": "old"},
                    {"name": "question", "color": "cccccc", "description": "old"},
                ]
            if "/labels/" in endpoint and k.get("method") == "PATCH":
                return {}
            raise AssertionError(f"unexpected api call: {endpoint} {k}")

        client.api.side_effect = api_side
        outcomes = sync_repository_labels_from_registry(
            client, "owner/repo", registry, apply=True
        )
        self.assertEqual(len(outcomes), 3)
        patches = [c for c in client.api.call_args_list if c.kwargs.get("method") == "PATCH"]
        self.assertEqual(len(patches), 3)
        self.assertTrue(any("new_name" in c.kwargs["fields"] for c in patches))
        posts = [c for c in client.api.call_args_list if c.kwargs.get("method") == "POST"]
        self.assertEqual(posts, [])

    def test_sync_idempotent_when_registry_already_matches(self):
        registry = Path(tempfile.mkdtemp()) / "labels.yml"
        registry.write_text(
            """
- name: Epic
  color: "5319e7"
  description: Issue type: epic.
""".strip()
            + "\n",
            encoding="utf-8",
        )
        client = Mock()

        def api_side(endpoint, *a, **k):
            if endpoint.endswith("/labels?per_page=100&page=1"):
                return [
                    {
                        "name": "Epic",
                        "color": "5319e7",
                        "description": "Issue type: epic.",
                    }
                ]
            raise AssertionError(f"unexpected api call: {endpoint} {k}")

        client.api.side_effect = api_side
        outcomes = sync_repository_labels_from_registry(
            client, "owner/repo", registry, apply=True
        )
        self.assertEqual(outcomes[0].state, "already-configured")
        self.assertEqual(len(client.api.call_args_list), 1)


class BootstrapLabelAndCommitTests(unittest.TestCase):
    def test_apply_seeds_epic_and_questions_with_type_labels(self):
        health = HealthReport(
            repo="akasper/greenfield",
            label_coverage_ok=False,
            missing_labels=["Epic", "Question"],
            binary_artifacts_tracked=0,
            branch_protection_enabled=False,
            open_epic_count=0,
            status="warn",
            goals_page_present=False,
            open_question_count=0,
            plate_config_present=True,
            plate_config_valid=True,
            curiosity_answers_present=False,
        )
        client = Mock()

        def api_side(endpoint, *a, **k):
            endpoint = str(endpoint)
            method = k.get("method", "GET")
            if endpoint == "repos/akasper/greenfield":
                return {"has_wiki": True, "default_branch": "main", "permissions": {"push": True}}
            if endpoint.endswith("/labels?per_page=100&page=1"):
                return []
            if endpoint.endswith("/labels") and method == "POST":
                return {}
            if "/issues?" in endpoint and "labels=Question" in endpoint:
                return []
            if endpoint == "repos/akasper/greenfield/issues" and method == "POST":
                return {"number": 1}
            if endpoint.startswith("repos/akasper/greenfield/contents/"):
                return {"type": "file"}
            if endpoint.startswith("repos/akasper/greenfield/branches/"):
                if endpoint.endswith("/main"):
                    return {"commit": {"sha": "abc123"}}
                raise GhApiError("HTTP 404")
            if endpoint == "repos/akasper/greenfield/git/refs" and method == "POST":
                return {}
            if endpoint == "repos/akasper/greenfield/git/ref/heads/main":
                return {"ref": "refs/heads/main"}
            return {}

        client.api.side_effect = api_side
        with tempfile.TemporaryDirectory() as tmp:
            template_root = Path(tmp) / "tpl"
            _write_template_tree(template_root, include_labels=True)
            with patch(
                "plate_core.bootstrap.get_health",
                return_value=health,
            ), patch(
                "plate_core.bootstrap.resolve_template_source",
                return_value=(template_root, "test"),
            ):
                run_bootstrap(
                    "akasper/greenfield",
                    apply_mode=True,
                    client=client,
                    local_root=Path(tempfile.mkdtemp()),
                )

        issue_posts = [
            c
            for c in client.api.call_args_list
            if c.args
            and c.args[0] == "repos/akasper/greenfield/issues"
            and c.kwargs.get("method") == "POST"
        ]
        epic_posts = [c for c in issue_posts if c.kwargs["fields"].get("labels") == ["Epic"]]
        question_posts = [
            c
            for c in issue_posts
            if c.kwargs["fields"].get("labels") == ["Question"]
        ]
        self.assertEqual(len(epic_posts), 1)
        self.assertEqual(len(question_posts), 3)

    def test_plate_init_commit_message_omits_plate_repo_issue_numbers(self):
        health = HealthReport(
            repo="akasper/new",
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
        client = Mock()

        def api_side(endpoint, *a, **k):
            endpoint = str(endpoint)
            method = k.get("method", "GET")
            if endpoint == "repos/akasper/new":
                return {"has_wiki": True, "default_branch": "main", "permissions": {"push": True}}
            if "/issues?" in endpoint and "labels=Question" in endpoint:
                return [{"title": "[Question]: existing"}]
            if endpoint.startswith("repos/akasper/new/contents/"):
                if ".plate" in endpoint and method == "PUT":
                    return {}
                return {"type": "file"}
            if endpoint.startswith("repos/akasper/new/branches/"):
                return {"name": "release"}
            return {}

        client.api.side_effect = api_side
        with tempfile.TemporaryDirectory() as tmp:
            template_root = Path(tmp) / "tpl"
            _write_template_tree(template_root, include_labels=False)
            with patch(
                "plate_core.bootstrap.get_health",
                return_value=health,
            ), patch(
                "plate_core.bootstrap.resolve_template_source",
                return_value=(template_root, "test"),
            ):
                run_bootstrap("akasper/new", apply_mode=True, client=client)

        plate_puts = [
            c
            for c in client.api.call_args_list
            if c.args and ".plate" in str(c.args[0]) and c.kwargs.get("method") == "PUT"
        ]
        self.assertTrue(plate_puts)
        message = plate_puts[0].kwargs.get("fields", {}).get("message", "")
        self.assertNotIn("#259", message)
        self.assertNotIn("Epic #", message)


if __name__ == "__main__":
    unittest.main()
