"""Regression: payload copy must omit __pycache__ and *.pyc (#1459)."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from plate_core.bootstrap import run_bootstrap
from plate_core.github_client import GhApiError
from plate_core.health import HealthReport
from plate_core.import_payload import import_payload, list_payload_relative_paths
from plate_core.template_payload import load_template_payload_manifest, should_include_template_file


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
        return {"sha": f"blob{store['blob_count']:04d}"}
    if method == "POST" and endpoint.endswith("/git/trees"):
        return {"sha": "newtree_sha"}
    if method == "POST" and endpoint.endswith("/git/commits"):
        store["commit_count"] = store.get("commit_count", 0) + 1
        return {"sha": f"commit{store['commit_count']:04d}"}
    if method == "PATCH" and "/git/refs/heads/" in endpoint:
        return {}
    return None


def _seed_template_root_with_bytecode(root: Path) -> None:
    root.joinpath("AGENTS.md").write_text("# AGENTS\n", encoding="utf-8")
    root.joinpath("README.md").write_text("# README\n", encoding="utf-8")
    (root / "docs" / "wiki").mkdir(parents=True)
    (root / "docs" / "wiki" / "Goals.md").write_text("# Goals\n", encoding="utf-8")
    plate = root / "scripts" / "plate"
    plate.mkdir(parents=True)
    (plate / "foo.py").write_text("# foo\n", encoding="utf-8")
    pycache = plate / "__pycache__"
    pycache.mkdir()
    (pycache / "x.cpython-311.pyc").write_bytes(b"\x00 bytecode")
    (root / "scripts" / "stray.pyc").write_bytes(b"\x00 stray")


def _assert_no_bytecode_under(root: Path) -> None:
    for path in root.rglob("*"):
        if "__pycache__" in path.parts:
            raise AssertionError(f"unexpected __pycache__ path: {path}")
        if path.is_file() and path.suffix in {".pyc", ".pyo"}:
            raise AssertionError(f"unexpected bytecode file: {path}")


def _tree_paths_from_mock(client: Mock) -> set[str]:
    paths: set[str] = set()
    for call in client.api.call_args_list:
        if not call.args or not str(call.args[0]).endswith("/git/trees"):
            continue
        if call.kwargs.get("method") != "POST":
            continue
        for entry in call.kwargs.get("fields", {}).get("tree", []):
            if isinstance(entry, dict) and entry.get("path"):
                paths.add(str(entry["path"]))
    return paths


class PayloadPycacheExclusionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = load_template_payload_manifest()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def test_installed_package_like_tree_omits_bytecode(self) -> None:
        """Simulate editable/install tree where scripts/plate/*.py was compiled."""
        plate = self.root / "scripts" / "plate"
        pycache = plate / "__pycache__"
        pycache.mkdir(parents=True)
        (plate / "foo.py").write_text("# stub\n", encoding="utf-8")
        (pycache / "foo.cpython-312.pyc").write_bytes(b"\x00\x00")

        rel_pyc = "scripts/plate/__pycache__/foo.cpython-312.pyc"
        rel_py = "scripts/plate/foo.py"

        self.assertFalse(should_include_template_file(rel_pyc, self.manifest))
        self.assertTrue(should_include_template_file(rel_py, self.manifest))

        listed = list_payload_relative_paths(self.root)
        self.assertIn(rel_py, listed)
        self.assertNotIn(rel_pyc, listed)
        self.assertEqual([p for p in listed if "pycache" in p or p.endswith(".pyc")], [])

    def test_greenfield_bootstrap_apply_skips_bytecode_in_remote_tree(self) -> None:
        """Grouped bootstrap commit must not upload __pycache__ or *.pyc paths."""
        client = Mock()
        ref_seen = {"count": 0}
        git_store: dict = {}

        def api_side(endpoint, *a, **k):
            endpoint = str(endpoint)
            method = k.get("method", "GET")
            if endpoint == "repos/akasper/greenfield-pycache":
                return {"has_wiki": False, "default_branch": "main", "permissions": {"push": True}}
            if endpoint == "repos/akasper/greenfield-pycache/git/ref/heads/main":
                ref_seen["count"] += 1
                if ref_seen["count"] < 2:
                    raise GhApiError("gh: Not Found (HTTP 404)")
                return {"object": {"sha": "abc123"}}
            if endpoint == "repos/akasper/greenfield-pycache/contents/README.md" and method == "PUT":
                return {"content": {"sha": "readme"}}
            if "/issues?" in endpoint and "labels=Question" in endpoint:
                return []
            if endpoint.startswith("repos/akasper/greenfield-pycache/contents/"):
                if method == "GET":
                    raise GhApiError("gh: Not Found (HTTP 404)")
                return {}
            if endpoint == "repos/akasper/greenfield-pycache/labels":
                return {}
            if endpoint == "repos/akasper/greenfield-pycache/issues" and method == "POST":
                return {"number": 1}
            if endpoint == "repos/akasper/greenfield-pycache/branches/main":
                return {"commit": {"sha": "abc123"}}
            if endpoint.startswith("repos/akasper/greenfield-pycache/branches/"):
                raise GhApiError("HTTP 404")
            if endpoint == "repos/akasper/greenfield-pycache/git/refs" and method == "POST":
                return {}
            git_resp = _bootstrap_git_data_side_effect(endpoint, method, git_store)
            if git_resp is not None:
                return git_resp
            return {}

        client.api.side_effect = api_side
        health = HealthReport(
            repo="akasper/greenfield-pycache",
            label_coverage_ok=False,
            missing_labels=["Feature"],
            binary_artifacts_tracked=0,
            branch_protection_enabled=False,
            open_epic_count=0,
            status="warn",
            goals_page_present=False,
            open_question_count=0,
            plate_config_present=False,
            plate_config_valid=False,
            curiosity_answers_present=False,
        )

        with tempfile.TemporaryDirectory() as template_tmp:
            template_root = Path(template_tmp)
            _seed_template_root_with_bytecode(template_root)
            with patch("plate_core.bootstrap.get_health", return_value=health):
                with patch(
                    "plate_core.bootstrap.resolve_template_source",
                    return_value=(template_root, "explicit_path"),
                ):
                    report = run_bootstrap(
                        "akasper/greenfield-pycache",
                        apply_mode=True,
                        client=client,
                    )

        copy_action = next(a for a in report.actions if a.name == "copy-template-payload")
        self.assertEqual(copy_action.state, "applied")
        tree_paths = _tree_paths_from_mock(client)
        self.assertIn("scripts/plate/foo.py", tree_paths)
        bytecode_paths = {p for p in tree_paths if "pycache" in p or p.endswith(".pyc")}
        self.assertEqual(bytecode_paths, set())

    def test_import_payload_apply_skips_bytecode_on_disk(self) -> None:
        """Local import-payload uses the same filtered path list as bootstrap."""
        with tempfile.TemporaryDirectory() as template_tmp, tempfile.TemporaryDirectory() as target_dir:
            template_root = Path(template_tmp)
            _seed_template_root_with_bytecode(template_root)
            with patch(
                "plate_core.import_payload.resolve_template_source",
                return_value=(template_root, "explicit_path"),
            ):
                report = import_payload(target_dir, strategy="safe", apply=True)

            self.assertTrue(report["ok"])
            target = Path(target_dir)
            self.assertTrue((target / "scripts" / "plate" / "foo.py").is_file())
            _assert_no_bytecode_under(target)


if __name__ == "__main__":
    unittest.main()
