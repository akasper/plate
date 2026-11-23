"""#1461: greenfield bootstrap payload ships .agentic/releases/unreleased/."""

from __future__ import annotations

import json
import tempfile
import unittest
from collections.abc import Callable
from pathlib import Path
from unittest.mock import Mock, patch

from plate_core.adoption import assess_adoption_readiness
from plate_core.bootstrap import run_bootstrap
from plate_core.github_client import GhApiError
from plate_core.health import HealthReport
from plate_core.import_payload import (
    MINIMAL_UNRELEASED_README,
    UNRELEASED_LAYOUT_README,
    import_payload,
    list_payload_relative_paths,
)
from plate_core.payload_surface import filter_plate_scripts
from plate_core.plate_config import get_plate_config_report
from plate_core.template_payload import resolve_template_source

from tests.test_bootstrap_greenfield_current_md import (
    _bootstrap_git_data_side_effect,
)


def _greenfield_health(repo: str) -> HealthReport:
    return HealthReport(
        repo=repo,
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


def _greenfield_bootstrap_api_side(
    repo: str,
    git_store: dict,
) -> Callable[..., object]:
    def api_side(endpoint, *a, **k):
        endpoint = str(endpoint)
        method = k.get("method", "GET")
        if endpoint == f"repos/{repo}":
            return {"has_wiki": True, "default_branch": "main", "permissions": {"push": True}}
        if "/issues?" in endpoint and "labels=Question" in endpoint:
            return []
        if endpoint.startswith(f"repos/{repo}/contents/"):
            if method == "GET":
                raise GhApiError("HTTP 404 Not Found")
            return {}
        if endpoint.startswith(f"repos/{repo}/branches/main"):
            return {"commit": {"sha": "abc123"}}
        if endpoint.startswith(f"repos/{repo}/branches/"):
            raise GhApiError("HTTP 404 Not Found")
        if endpoint == f"repos/{repo}/git/refs" and method == "POST":
            return {}
        if method == "POST" and endpoint.endswith("/git/blobs"):
            git_store["_last_blob_fields"] = k.get("fields") or {}
        if method == "POST" and endpoint.endswith("/git/trees"):
            git_store["_last_tree_fields"] = k.get("fields") or {}
        git_resp = _bootstrap_git_data_side_effect(endpoint, method, git_store)
        if git_resp is not None:
            return git_resp
        return {}

    return api_side


def _run_greenfield_bootstrap_apply(repo: str) -> dict[str, bytes]:
    client = Mock()
    git_store: dict = {}
    template_root, _source = resolve_template_source()
    client.api.side_effect = _greenfield_bootstrap_api_side(repo, git_store)
    with patch("plate_core.bootstrap.get_health", return_value=_greenfield_health(repo)), patch(
        "plate_core.bootstrap.resolve_template_source",
        return_value=(template_root, "bundled"),
    ):
        run_bootstrap(repo, apply_mode=True, client=client)
    return git_store.get("tree_paths") or {}


class BootstrapUnreleasedLayout1461Tests(unittest.TestCase):
    def test_template_readme_matches_minimal_constant(self):
        template_root, _ = resolve_template_source()
        payload_text = (template_root / UNRELEASED_LAYOUT_README).read_text(encoding="utf-8")
        self.assertEqual(payload_text, MINIMAL_UNRELEASED_README)

    def test_payload_paths_and_inventory_include_unreleased_readme(self):
        template_root, _ = resolve_template_source()
        rel_paths, _ = filter_plate_scripts(
            list_payload_relative_paths(template_root),
            "posix",
        )
        self.assertIn(UNRELEASED_LAYOUT_README, rel_paths)
        readme = template_root / UNRELEASED_LAYOUT_README
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
        self.assertIn(UNRELEASED_LAYOUT_README, inv_paths)
        entry = next(
            e for e in inventory_data["files"] if e["path"] == UNRELEASED_LAYOUT_README
        )
        self.assertEqual(entry["classification"], "copy_to_downstream")

    def test_grouped_commit_includes_unreleased_readme(self):
        """Greenfield bootstrap apply copies unreleased README in the grouped commit."""
        tree_paths = _run_greenfield_bootstrap_apply("akasper/gf-unreleased")
        self.assertIn(UNRELEASED_LAYOUT_README, tree_paths)
        text = tree_paths[UNRELEASED_LAYOUT_README].decode("utf-8")
        self.assertEqual(text, MINIMAL_UNRELEASED_README)

    def test_bootstrap_materialized_tree_is_core_ready_for_releases(self):
        """Filesystem tree from grouped bootstrap passes agentic_releases and core_ready."""
        tree_paths = _run_greenfield_bootstrap_apply("akasper/gf-adopt-ready")
        self.assertIn(UNRELEASED_LAYOUT_README, tree_paths)
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

    def test_fresh_dry_run_lists_unreleased_readme_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = import_payload(tmp, strategy="safe", dry_run=True)
        creates = [
            p
            for p in report.get("would_create") or []
            if UNRELEASED_LAYOUT_README in p
        ]
        self.assertEqual(len(creates), 1, msg=report.get("would_create"))

    def test_conservative_skips_identical_seeded_unreleased_readme(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            readme = root / UNRELEASED_LAYOUT_README
            readme.parent.mkdir(parents=True, exist_ok=True)
            readme.write_text(MINIMAL_UNRELEASED_README, encoding="utf-8")
            report = import_payload(tmp, strategy="conservative", dry_run=True)
        self.assertNotIn(
            UNRELEASED_LAYOUT_README,
            report.get("would_conflict") or [],
        )
        self.assertEqual(
            report.get("next_command"),
            "gh plate import-payload --apply --strategy conservative",
        )

    def test_conservative_preserves_custom_unreleased_readme(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            readme = root / UNRELEASED_LAYOUT_README
            readme.parent.mkdir(parents=True, exist_ok=True)
            readme.write_text("# Custom adopter unreleased guide\n", encoding="utf-8")
            report = import_payload(tmp, strategy="conservative", dry_run=True)
        self.assertNotIn(
            UNRELEASED_LAYOUT_README,
            report.get("would_conflict") or [],
        )
        self.assertIn(UNRELEASED_LAYOUT_README, report.get("would_skip") or [])
        self.assertEqual(
            report.get("next_command"),
            "gh plate import-payload --apply --strategy conservative",
        )


if __name__ == "__main__":
    unittest.main()
