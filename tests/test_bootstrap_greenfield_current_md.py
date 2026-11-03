"""#1322: greenfield bootstrap seeds CURRENT.md for validate_plate_repo."""

from __future__ import annotations

import base64
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from plate_core.bootstrap import (
    _maybe_queue_bootstrap_current_md,
    run_bootstrap,
)
from plate_core.github_client import GhApiError
from plate_core.health import HealthReport
from plate_core.import_payload import import_payload
from plate_core.template_payload import payload_root, resolve_template_source


def _bootstrap_git_data_side_effect(
    endpoint: str,
    method: str,
    store: dict,
    *,
    parent_commit: str = "abc123",
) -> object | None:
    if "/git/ref/heads/" in endpoint and method == "GET":
        return {"object": {"sha": parent_commit}}
    if "/git/commits/" in endpoint and method == "GET":
        return {"tree": {"sha": "basetree_sha"}}
    if method == "POST" and endpoint.endswith("/git/blobs"):
        store["blob_count"] = store.get("blob_count", 0) + 1
        sha = f"blob{store['blob_count']:04d}"
        fields = store.get("_last_blob_fields") or {}
        content_b64 = fields.get("content", "")
        if content_b64:
            store.setdefault("blobs", {})[sha] = base64.b64decode(content_b64)
        return {"sha": sha}
    if method == "POST" and endpoint.endswith("/git/trees"):
        tree = store.get("_last_tree_fields", {}).get("tree", [])
        paths: dict[str, bytes] = {}
        blobs = store.get("blobs", {})
        for entry in tree:
            if isinstance(entry, dict):
                path = entry.get("path")
                blob_sha = entry.get("sha")
                if isinstance(path, str) and isinstance(blob_sha, str) and blob_sha in blobs:
                    paths[path] = blobs[blob_sha]
        store["tree_paths"] = paths
        return {"sha": "newtree_sha"}
    if method == "POST" and endpoint.endswith("/git/commits"):
        store["commit_count"] = store.get("commit_count", 0) + 1
        return {"sha": f"commit{store['commit_count']:04d}"}
    if method == "PATCH" and "/git/refs/heads/" in endpoint:
        return {}
    return None


def _bash_executable() -> str | None:
    found = shutil.which("bash")
    if found:
        return found
    candidate = Path(r"C:\Program Files\Git\bin\bash.exe")
    if candidate.is_file():
        return str(candidate)
    return None


class BootstrapGreenfieldCurrentMdTests(unittest.TestCase):
    def test_grouped_commit_includes_minimal_current_md(self):
        """Greenfield bootstrap apply queues CURRENT.md in the grouped payload commit (#1322)."""
        health = HealthReport(
            repo="akasper/gf-current",
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
        git_store: dict = {}
        template_root, _source = resolve_template_source()

        def api_side(endpoint, *a, **k):
            endpoint = str(endpoint)
            method = k.get("method", "GET")
            if endpoint == "repos/akasper/gf-current":
                return {"has_wiki": True, "default_branch": "main", "permissions": {"push": True}}
            if "/issues?" in endpoint and "labels=Question" in endpoint:
                return []
            if endpoint.startswith("repos/akasper/gf-current/contents/"):
                if "CURRENT.md" in endpoint and method == "GET":
                    raise GhApiError("HTTP 404 Not Found")
                if method == "GET":
                    raise GhApiError("HTTP 404 Not Found")
                return {}
            if endpoint.startswith("repos/akasper/gf-current/branches/main"):
                return {"commit": {"sha": "abc123"}}
            if endpoint.startswith("repos/akasper/gf-current/branches/"):
                raise GhApiError("HTTP 404 Not Found")
            if endpoint == "repos/akasper/gf-current/git/refs" and method == "POST":
                return {}
            if method == "POST" and endpoint.endswith("/git/blobs"):
                git_store["_last_blob_fields"] = k.get("fields") or {}
            if method == "POST" and endpoint.endswith("/git/trees"):
                git_store["_last_tree_fields"] = k.get("fields") or {}
            git_resp = _bootstrap_git_data_side_effect(endpoint, method, git_store)
            if git_resp is not None:
                return git_resp
            return {}

        client.api.side_effect = api_side
        with patch("plate_core.bootstrap.get_health", return_value=health), patch(
            "plate_core.bootstrap.resolve_template_source",
            return_value=(template_root, "bundled"),
        ):
            run_bootstrap("akasper/gf-current", apply_mode=True, client=client)

        tree_paths = git_store.get("tree_paths") or {}
        self.assertIn("CURRENT.md", tree_paths)
        text = tree_paths["CURRENT.md"].decode("utf-8")
        self.assertIn("Adoption note", text)
        self.assertIn(".agentic/releases/", text)
        self.assertNotIn(
            "Project-specific CI commands are not defined by the generic template",
            text,
        )

    def test_validate_passes_on_fresh_greenfield_tree(self):
        """Scaffold plus bootstrap CURRENT seed satisfies scripts/validate_plate_repo.sh."""
        bash = _bash_executable()
        if bash is None:
            self.skipTest("bash is not on PATH")
        script = payload_root() / "scripts" / "validate_plate_repo.sh"
        client = Mock()

        def api_side(endpoint, *a, **k):
            endpoint = str(endpoint)
            if "CURRENT.md" in endpoint:
                raise GhApiError("HTTP 404 Not Found")
            if "playwright.config.ts" in endpoint or endpoint.endswith("tests/e2e"):
                raise GhApiError("HTTP 404 Not Found")
            return {"type": "file"}

        client.api.side_effect = api_side

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            applied = import_payload(tmp, strategy="safe", apply=True)
            self.assertTrue(applied["ok"])
            current = root / "CURRENT.md"
            self.assertTrue(current.is_file())
            current.unlink()

            pending: list[tuple[str, bytes]] = []
            for rel in applied.get("created") or []:
                path = root / rel
                if path.is_file():
                    pending.append((rel, path.read_bytes()))
            self.assertTrue(
                _maybe_queue_bootstrap_current_md("owner/repo", client, "abc123", pending)
            )
            current_bytes = next(data for rel, data in pending if rel == "CURRENT.md")
            current.write_bytes(current_bytes)

            result = subprocess.run(
                [bash, str(script), str(root)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_seed_epic_attaches_initial_milestone(self):
        """Issue #1322 part 2: bootstrap Epic uses Initial milestone (already on main)."""
        health = HealthReport(
            repo="akasper/gf-milestone",
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
        client = Mock()
        template_root, _source = resolve_template_source()

        def api_side(endpoint, *a, **k):
            endpoint = str(endpoint)
            method = k.get("method", "GET")
            if endpoint == "repos/akasper/gf-milestone":
                return {"has_wiki": True, "default_branch": "main", "permissions": {"push": True}}
            if endpoint == "repos/akasper/gf-milestone/milestones?state=open&per_page=100":
                return []
            if endpoint == "repos/akasper/gf-milestone/milestones" and method == "POST":
                return {"number": 3, "title": "Initial milestone"}
            if "/issues?" in endpoint and "labels=Question" in endpoint:
                return []
            if endpoint == "repos/akasper/gf-milestone/issues" and method == "POST":
                return {"number": 1}
            if endpoint.startswith("repos/akasper/gf-milestone/contents/"):
                if method == "GET":
                    raise GhApiError("HTTP 404 Not Found")
                return {}
            if endpoint.startswith("repos/akasper/gf-milestone/branches/main"):
                return {"commit": {"sha": "abc123"}}
            if endpoint.startswith("repos/akasper/gf-milestone/branches/"):
                raise GhApiError("HTTP 404 Not Found")
            if endpoint == "repos/akasper/gf-milestone/git/refs" and method == "POST":
                return {}
            git_resp = _bootstrap_git_data_side_effect(endpoint, method, {})
            if git_resp is not None:
                return git_resp
            return {}

        client.api.side_effect = api_side
        with patch("plate_core.bootstrap.get_health", return_value=health), patch(
            "plate_core.bootstrap.resolve_template_source",
            return_value=(template_root, "bundled"),
        ):
            run_bootstrap("akasper/gf-milestone", apply_mode=True, client=client)

        epic_posts = [
            c
            for c in client.api.call_args_list
            if c.args
            and c.args[0] == "repos/akasper/gf-milestone/issues"
            and c.kwargs.get("method") == "POST"
            and c.kwargs.get("fields", {}).get("labels") == ["Epic"]
        ]
        self.assertEqual(len(epic_posts), 1)
        self.assertEqual(epic_posts[0].kwargs["fields"].get("milestone"), 3)
