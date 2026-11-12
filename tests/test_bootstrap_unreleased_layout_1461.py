"""#1461: greenfield bootstrap payload ships .agentic/releases/unreleased/."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from plate_core.adoption import assess_adoption_readiness
from plate_core.bootstrap import run_bootstrap
from plate_core.health import HealthReport
from plate_core.import_payload import list_payload_relative_paths
from plate_core.payload_surface import filter_plate_scripts
from plate_core.plate_config import get_plate_config_report
from plate_core.template_payload import resolve_template_source

from tests.test_bootstrap_greenfield_current_md import (
    _bootstrap_git_data_side_effect,
)


UNRELEASED_README = ".agentic/releases/unreleased/README.md"


class BootstrapUnreleasedLayout1461Tests(unittest.TestCase):
    def test_payload_paths_and_inventory_include_unreleased_readme(self):
        template_root, _ = resolve_template_source()
        rel_paths, _ = filter_plate_scripts(
            list_payload_relative_paths(template_root),
            "posix",
        )
        self.assertIn(UNRELEASED_README, rel_paths)
        readme = template_root / UNRELEASED_README
        self.assertTrue(readme.is_file(), msg=str(readme))

        inv_path = (
            Path(__file__).resolve().parent.parent
            / "src"
            / "plate_core"
            / "data"
            / "template_payload_inventory.json"
        )
        inventory_data = json.loads(inv_path.read_text(encoding="utf-8"))
        inv_paths = {entry["path"] for entry in inventory_data.get("files") or []}
        self.assertIn(UNRELEASED_README, inv_paths)
        entry = next(e for e in inventory_data["files"] if e["path"] == UNRELEASED_README)
        self.assertEqual(entry["classification"], "copy_to_downstream")

    def test_grouped_commit_includes_unreleased_readme(self):
        """Greenfield bootstrap apply copies unreleased README in the grouped commit."""
        from plate_core.github_client import GhApiError

        health = HealthReport(
            repo="akasper/gf-unreleased",
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
            if endpoint == "repos/akasper/gf-unreleased":
                return {"has_wiki": True, "default_branch": "main", "permissions": {"push": True}}
            if "/issues?" in endpoint and "labels=Question" in endpoint:
                return []
            if endpoint.startswith("repos/akasper/gf-unreleased/contents/"):
                if method == "GET":
                    raise GhApiError("HTTP 404 Not Found")
                return {}
            if endpoint.startswith("repos/akasper/gf-unreleased/branches/main"):
                return {"commit": {"sha": "abc123"}}
            if endpoint.startswith("repos/akasper/gf-unreleased/branches/"):
                raise GhApiError("HTTP 404 Not Found")
            if endpoint == "repos/akasper/gf-unreleased/git/refs" and method == "POST":
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
            run_bootstrap("akasper/gf-unreleased", apply_mode=True, client=client)

        tree_paths = git_store.get("tree_paths") or {}
        self.assertIn(UNRELEASED_README, tree_paths)
        text = tree_paths[UNRELEASED_README].decode("utf-8")
        self.assertIn("unreleased fragments", text)
        self.assertNotIn("import-payload", text.lower())

    def test_bootstrap_materialized_tree_is_core_ready_for_releases(self):
        """Filesystem tree from grouped bootstrap passes agentic_releases and core_ready."""
        from plate_core.github_client import GhApiError

        health = HealthReport(
            repo="akasper/gf-adopt-ready",
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
            if endpoint == "repos/akasper/gf-adopt-ready":
                return {"has_wiki": True, "default_branch": "main", "permissions": {"push": True}}
            if "/issues?" in endpoint and "labels=Question" in endpoint:
                return []
            if endpoint.startswith("repos/akasper/gf-adopt-ready/contents/"):
                if method == "GET":
                    raise GhApiError("HTTP 404 Not Found")
                return {}
            if endpoint.startswith("repos/akasper/gf-adopt-ready/branches/main"):
                return {"commit": {"sha": "abc123"}}
            if endpoint.startswith("repos/akasper/gf-adopt-ready/branches/"):
                raise GhApiError("HTTP 404 Not Found")
            if endpoint == "repos/akasper/gf-adopt-ready/git/refs" and method == "POST":
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
            run_bootstrap("akasper/gf-adopt-ready", apply_mode=True, client=client)

        tree_paths = git_store.get("tree_paths") or {}
        self.assertIn(UNRELEASED_README, tree_paths)
        self.assertIn(".plate", tree_paths)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel, data in tree_paths.items():
                dest = root / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(data)
            rep = get_plate_config_report(root)
            self.assertTrue(rep.valid, msg=getattr(rep, "errors", None))
            ready = assess_adoption_readiness(root, include_optional=False)
            checks = {c["id"]: c for c in ready.get("checks") or []}
            self.assertTrue(
                checks["agentic_releases"]["ok"],
                msg=checks["agentic_releases"],
            )
            self.assertTrue(ready.get("core_ready"), msg=ready)


if __name__ == "__main__":
    unittest.main()
