import base64
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from plate_core.bootstrap import detect_adoption_mode, run_bootstrap
from plate_core.payload_surface import prepare_copied_text
from plate_core.github_client import GhApiError
from plate_core.health import HealthReport


def _write_template_file(root: Path, rel: str, content: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _bootstrap_git_data_side_effect(
    endpoint: str,
    method: str,
    store: dict,
    *,
    parent_commit: str = "abc123",
) -> object | None:
    """Mock GitHub Git Data API calls used for grouped bootstrap commits (#1277)."""
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


def _make_template_root() -> tempfile.TemporaryDirectory:
    tempdir = tempfile.TemporaryDirectory()
    root = Path(tempdir.name)
    _write_template_file(root, "AGENTS.md", "# AGENTS\n")
    _write_template_file(root, "README.md", "# README\n")
    _write_template_file(root, "docs/wiki/Goals.md", "# Goals\n")
    return tempdir


class BootstrapTests(unittest.TestCase):
    def test_namespaced_goals_is_not_docs_without_goals(self):
        """Proves: docs/plate/wiki/Goals.md suppresses local:docs_without_Goals (#1022)."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            goals = root / "docs" / "plate" / "wiki"
            goals.mkdir(parents=True)
            (goals / "Goals.md").write_text("# Goals\n", encoding="utf-8")
            _adopt, signals = detect_adoption_mode(local_root=root)
        self.assertNotIn("local:docs_without_Goals", signals)

    @patch("plate_core.bootstrap.get_health")
    def test_dry_run_reports_planned_actions(self, mock_get_health):
        mock_get_health.return_value = HealthReport(
            repo="akasper/plate_core",
            label_coverage_ok=False,
            missing_labels=["Feature", "Epic"],
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
        client = Mock()

        def api_side(endpoint, *a, **k):
            endpoint = str(endpoint)
            if endpoint == "repos/akasper/plate_core":
                return {"has_wiki": False, "default_branch": "main"}
            if "/issues?" in endpoint and "labels=Question" in endpoint:
                return []
            if endpoint.startswith("repos/akasper/plate_core/contents/"):
                return {"type": "file"}
            return {}

        client.api.side_effect = api_side
        with _make_template_root() as tmpdir:
            template_root = Path(tmpdir)
            with patch(
                "plate_core.bootstrap.resolve_template_source",
                return_value=(template_root, "explicit_path"),
            ):
                report = run_bootstrap("akasper/plate_core", apply_mode=False, client=client)
        states = {a.name: a.state for a in report.actions}
        self.assertEqual(states["copy-template-payload"], "planned")
        self.assertEqual(states["enable-wiki"], "planned")
        self.assertEqual(states["branch-protection"], "manual-required")
        copy_action = next((a for a in report.actions if a.name == "copy-template-payload"), None)
        self.assertIsNotNone(copy_action, "copy-template-payload action must be present")
        self.assertIn("Would copy", copy_action.detail)
        self.assertIn("missing template payload", copy_action.detail)
        plate_action = next((a for a in report.actions if a.name == "init-plate-config"), None)
        self.assertIsNotNone(plate_action, "init-plate-config action must be present for #259")
        self.assertEqual(plate_action.state, "planned")
        self.assertIn("root .plate", plate_action.detail)
        seed_action = next((a for a in report.actions if a.name == "seed-initial-questions"), None)
        self.assertIsNotNone(seed_action, "seed-initial-questions action must be present")
        self.assertEqual(seed_action.state, "planned")
        self.assertIn("Seed", seed_action.detail)

    @patch("plate_core.bootstrap.get_health")
    def test_apply_seed_writes_first_qa_marker(self, mock_get_health):
        """Proves: bootstrap apply seed writes .agentic/adoption first_qa marker (#951)."""
        from plate_core.adoption import first_qa_seed_status

        mock_get_health.return_value = HealthReport(
            repo="akasper/new-repo",
            label_coverage_ok=True,
            missing_labels=[],
            binary_artifacts_tracked=0,
            branch_protection_enabled=True,
            open_epic_count=1,
            status="pass",
            goals_page_present=True,
            open_question_count=0,
            plate_config_present=True,
            plate_config_valid=True,
            curiosity_answers_present=False,
        )
        client = Mock()

        def api_side(endpoint, *a, **k):
            endpoint = str(endpoint)
            if endpoint == "repos/akasper/new-repo":
                return {"has_wiki": True, "default_branch": "main"}
            if "/issues?" in endpoint and "labels=Question" in endpoint:
                return []
            if endpoint == "repos/akasper/new-repo/issues" and k.get("method") == "POST":
                return {"number": 1}
            if endpoint.startswith("repos/akasper/new-repo/contents/"):
                return {"type": "file"}
            return {}

        client.api.side_effect = api_side
        with tempfile.TemporaryDirectory() as local_tmp:
            local_root = Path(local_tmp)
            with _make_template_root() as tmpdir:
                template_root = Path(tmpdir)
                with patch(
                    "plate_core.bootstrap.resolve_template_source",
                    return_value=(template_root, "explicit_path"),
                ):
                    report = run_bootstrap(
                        "akasper/new-repo",
                        apply_mode=True,
                        client=client,
                        local_root=local_root,
                    )
            seed = next(a for a in report.actions if a.name == "seed-initial-questions")
            self.assertEqual(seed.state, "applied")
            self.assertIn("first_qa marker", seed.detail)
            status = first_qa_seed_status(local_root)
            self.assertTrue(status["seeded"])
            self.assertGreaterEqual(status["count"], 3)

    @patch("plate_core.bootstrap.get_health")
    def test_apply_already_seeded_syncs_first_qa_marker(self, mock_get_health):
        """Proves: apply with existing Questions syncs offline first_qa marker (#951)."""
        from plate_core.adoption import first_qa_seed_status

        mock_get_health.return_value = HealthReport(
            repo="akasper/mature",
            label_coverage_ok=True,
            missing_labels=[],
            binary_artifacts_tracked=0,
            branch_protection_enabled=True,
            open_epic_count=2,
            status="pass",
            goals_page_present=True,
            open_question_count=3,
            plate_config_present=True,
            plate_config_valid=True,
            curiosity_answers_present=False,
        )
        client = Mock()

        def api_side(endpoint, *a, **k):
            endpoint = str(endpoint)
            if endpoint == "repos/akasper/mature":
                return {"has_wiki": True, "default_branch": "main", "size": 9000}
            if "/issues?" in endpoint and "labels=Question" in endpoint:
                return [
                    {"title": "[Question]: What is the primary purpose or value proposition of this software?"},
                    {"title": "[Question]: Who are the primary users or customers of this software?"},
                    {"title": "[Question]: What are the biggest risks or unknowns for this project right now?"},
                ]
            if endpoint.startswith("repos/akasper/mature/contents/"):
                return {"type": "file"}
            if "/issues?" in endpoint and "labels=Epic" in endpoint:
                return [{"number": 1}]
            return {}

        client.api.side_effect = api_side
        with tempfile.TemporaryDirectory() as local_tmp:
            local_root = Path(local_tmp)
            with _make_template_root() as tmpdir:
                template_root = Path(tmpdir)
                with patch(
                    "plate_core.bootstrap.resolve_template_source",
                    return_value=(template_root, "explicit_path"),
                ):
                    report = run_bootstrap(
                        "akasper/mature",
                        apply_mode=True,
                        client=client,
                        adopt=True,
                        local_root=local_root,
                    )
            seed = next(a for a in report.actions if a.name == "seed-initial-questions")
            self.assertEqual(seed.state, "already-configured")
            self.assertIn("marker", seed.detail.lower())
            self.assertTrue(first_qa_seed_status(local_root)["seeded"])

    def test_detect_adoption_mode_force_and_heuristics(self):
        """#619 pure detector: flags win; mature signals flip adopt when .plate missing."""
        health = HealthReport(
            repo="o/r",
            label_coverage_ok=False,
            missing_labels=[],
            binary_artifacts_tracked=0,
            branch_protection_enabled=False,
            open_epic_count=2,
            status="warn",
            goals_page_present=False,
            open_question_count=1,
            plate_config_present=False,
            plate_config_valid=False,
            curiosity_answers_present=False,
        )
        adopt, signals = detect_adoption_mode(
            health=health,
            repo_obj={"size": 9000, "open_issues_count": 12, "description": "app"},
            force_adopt=None,
            local_root=Path(tempfile.mkdtemp()),
        )
        self.assertTrue(adopt)
        self.assertTrue(any("open_epics" in s for s in signals))

        forced, sig = detect_adoption_mode(force_adopt=True)
        self.assertTrue(forced)
        self.assertIn("flag:--adopt", sig)

        green, gsig = detect_adoption_mode(force_adopt=False, health=health)
        self.assertFalse(green)
        self.assertIn("flag:greenfield", gsig)

    @patch("plate_core.bootstrap.get_health")
    def test_adopt_mode_tailors_copy_detail_and_next_steps(self, mock_get_health):
        """#619: --adopt surfaces import-payload guidance and next_steps."""
        mock_get_health.return_value = HealthReport(
            repo="akasper/mature",
            label_coverage_ok=True,
            missing_labels=[],
            binary_artifacts_tracked=0,
            branch_protection_enabled=True,
            open_epic_count=3,
            status="pass",
            goals_page_present=False,
            open_question_count=2,
            plate_config_present=True,
            plate_config_valid=True,
            curiosity_answers_present=False,
        )
        client = Mock()

        def api_side(endpoint, *a, **k):
            endpoint = str(endpoint)
            if endpoint == "repos/akasper/mature":
                return {
                    "has_wiki": True,
                    "default_branch": "main",
                    "size": 8000,
                    "open_issues_count": 20,
                    "description": "mature app",
                }
            if "/issues?" in endpoint and "labels=Question" in endpoint:
                return [{"title": "[Question]: existing"}]
            if "/branches/" in endpoint:
                return {"name": "release"}
            return {}

        client.api.side_effect = api_side
        with _make_template_root() as tmpdir:
            template_root = Path(tmpdir)
            with patch(
                "plate_core.bootstrap.resolve_template_source",
                return_value=(template_root, "explicit_path"),
            ):
                report = run_bootstrap(
                    "akasper/mature",
                    apply_mode=False,
                    client=client,
                    adopt=True,
                )
        self.assertTrue(report.adoption_mode)
        self.assertTrue(report.next_steps)
        self.assertTrue(any("import-payload" in s for s in report.next_steps))
        copy_action = next(a for a in report.actions if a.name == "copy-template-payload")
        self.assertIn("import-payload", copy_action.detail)
        epic = next(a for a in report.actions if a.name == "create-initial-epic")
        self.assertEqual(epic.state, "already-configured")
        seed = next(a for a in report.actions if a.name == "seed-initial-questions")
        self.assertEqual(seed.state, "already-configured")

    @patch("plate_core.bootstrap.get_health")
    def test_apply_wiki_passes_bool_not_string(self, mock_get_health):
        """has_wiki must be sent as Python bool True so GhClient uses -F and gh
        interprets it as a JSON boolean, not the string 'true'."""
        mock_get_health.return_value = HealthReport(
            repo="akasper/test-repo",
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

        def api_side(endpoint, *a, **k):
            endpoint = str(endpoint)
            method = k.get("method", "GET")
            if endpoint == "repos/akasper/test-repo":
                return {"has_wiki": False, "default_branch": "main"}
            if "/issues?" in endpoint and "labels=Question" in endpoint:
                return []
            if endpoint.startswith("repos/akasper/test-repo/contents/"):
                if "README.md" in endpoint and method == "GET":
                    return {"type": "file"}
                if method == "GET":
                    raise GhApiError("HTTP 404 Not Found")
                return {}
            if endpoint == "repos/akasper/test-repo/labels":
                return {}
            if endpoint == "repos/akasper/test-repo/issues":
                return {}
            if endpoint == "repos/akasper/test-repo/branches/main":
                return {"commit": {"sha": "abc123"}}
            if endpoint.startswith("repos/akasper/test-repo/branches/"):
                raise GhApiError("HTTP 404 Not Found")
            if endpoint == "repos/akasper/test-repo/git/refs":
                return {}
            git_resp = _bootstrap_git_data_side_effect(endpoint, method, git_store)
            if git_resp is not None:
                return git_resp
            return {}

        client.api.side_effect = api_side

        with _make_template_root() as tmpdir:
            template_root = Path(tmpdir)
            with patch(
                "plate_core.bootstrap.resolve_template_source",
                return_value=(template_root, "explicit_path"),
            ):
                report = run_bootstrap("akasper/test-repo", apply_mode=True, client=client)

        # Find the PATCH call for has_wiki
        patch_calls = [
            call for call in client.api.call_args_list
            if call.args and call.args[0] == "repos/akasper/test-repo"
            and call.kwargs.get("method") == "PATCH"
        ]
        self.assertTrue(patch_calls, "Expected a PATCH call for has_wiki")
        fields = patch_calls[0].kwargs.get("fields", {})
        self.assertIs(fields.get("has_wiki"), True, "has_wiki must be Python bool True, not a string")

        copy_action = next((a for a in report.actions if a.name == "copy-template-payload"), None)
        self.assertIsNotNone(copy_action)
        self.assertEqual(copy_action.state, "applied")

        # Verify copied template files were uploaded in one grouped commit (#1277).
        template_puts = [
            call for call in client.api.call_args_list
            if call.args and "repos/akasper/test-repo/contents/" in str(call.args[0])
            and call.kwargs.get("method") == "PUT"
        ]
        self.assertFalse(template_puts, "Template payload should use Git Data API, not per-file contents PUT")

        commit_posts = [
            call for call in client.api.call_args_list
            if call.args
            and str(call.args[0]).endswith("/git/commits")
            and call.kwargs.get("method") == "POST"
        ]
        self.assertEqual(len(commit_posts), 1, "Expected one grouped bootstrap commit for template payload")
        commit_message = commit_posts[0].kwargs.get("fields", {}).get("message", "")
        self.assertIn("template payload", commit_message.lower())
        blob_posts = [
            call for call in client.api.call_args_list
            if call.args and str(call.args[0]).endswith("/git/blobs") and call.kwargs.get("method") == "POST"
        ]
        self.assertGreaterEqual(len(blob_posts), 2)

        # Verify 3 starter Question POSTs were issued (new Feature #153 behavior)
        question_posts = [
            call for call in client.api.call_args_list
            if call.args and "repos/akasper/test-repo/issues" in str(call.args[0])
            and call.kwargs.get("method") == "POST"
            and "Question" in str(call.kwargs.get("fields", {}).get("labels", []))
        ]
        self.assertEqual(len(question_posts), 3, "Expected exactly 3 POSTs to seed starter Questions on apply when none exist")

        commit_tree = [
            call
            for call in client.api.call_args_list
            if call.args and str(call.args[0]).endswith("/git/trees") and call.kwargs.get("method") == "POST"
        ]
        self.assertTrue(commit_tree, "Expected tree creation for grouped bootstrap commit")
        tree_entries = commit_tree[0].kwargs.get("fields", {}).get("tree", [])
        tree_paths = {entry.get("path") for entry in tree_entries if isinstance(entry, dict)}
        self.assertIn("AGENTS.md", tree_paths)
        self.assertIn("docs/wiki/Goals.md", tree_paths)
        self.assertIn(".plate", tree_paths)
        self.assertNotIn("README.md", tree_paths)

        plate_puts = [
            call for call in client.api.call_args_list
            if call.args and "contents/.plate" in str(call.args[0])
            and call.kwargs.get("method") == "PUT"
        ]
        self.assertFalse(plate_puts, ".plate should be included in the grouped bootstrap commit")

    @patch("plate_core.bootstrap.get_health")
    def test_apply_creates_initial_commit_on_empty_repository(self, mock_get_health):
        mock_get_health.return_value = HealthReport(
            repo="akasper/empty-repo",
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
        client = Mock()
        ref_seen = {"count": 0}
        git_store: dict = {}

        def api_side(endpoint, *a, **k):
            endpoint = str(endpoint)
            method = k.get("method", "GET")
            if endpoint == "repos/akasper/empty-repo":
                return {"has_wiki": False, "default_branch": "main", "permissions": {"push": True}}
            if endpoint == "repos/akasper/empty-repo/git/ref/heads/main":
                ref_seen["count"] += 1
                if ref_seen["count"] < 2:
                    raise GhApiError("gh: Not Found (HTTP 404)")
                return {"object": {"sha": "abc123"}}
            if endpoint == "repos/akasper/empty-repo/contents/README.md" and method == "PUT":
                return {"content": {"sha": "readme"}}
            if "/issues?" in endpoint and "labels=Question" in endpoint:
                return []
            if endpoint.startswith("repos/akasper/empty-repo/contents/"):
                if method == "GET":
                    raise GhApiError("gh: Not Found (HTTP 404)")
                return {}
            if endpoint == "repos/akasper/empty-repo/labels":
                return {}
            if endpoint == "repos/akasper/empty-repo/issues" and method == "POST":
                return {"number": 1}
            if endpoint == "repos/akasper/empty-repo/branches/main":
                return {"commit": {"sha": "abc123"}}
            if endpoint.startswith("repos/akasper/empty-repo/branches/"):
                raise GhApiError("HTTP 404")
            if endpoint == "repos/akasper/empty-repo/git/refs" and method == "POST":
                return {}
            git_resp = _bootstrap_git_data_side_effect(endpoint, method, git_store)
            if git_resp is not None:
                return git_resp
            return {}

        client.api.side_effect = api_side
        with _make_template_root() as tmpdir:
            template_root = Path(tmpdir)
            with patch(
                "plate_core.bootstrap.resolve_template_source",
                return_value=(template_root, "explicit_path"),
            ):
                report = run_bootstrap("akasper/empty-repo", apply_mode=True, client=client)

        readme_puts = [
            c
            for c in client.api.call_args_list
            if c.args and "contents/README.md" in str(c.args[0]) and c.kwargs.get("method") == "PUT"
        ]
        self.assertTrue(readme_puts, "Expected initial README commit on empty repo")
        self.assertEqual(ref_seen["count"], 3, "Should verify default branch ref after seeding and grouped commit")
        plate_action = next(a for a in report.actions if a.name == "init-plate-config")
        self.assertEqual(plate_action.state, "applied")

    @patch("plate_core.bootstrap.get_health")
    def test_apply_creates_initial_commit_when_ref_lookup_returns_empty_repo_409(self, mock_get_health):
        """Empty repos may return HTTP 409 (not 404) on git/ref lookup (#1152)."""
        mock_get_health.return_value = HealthReport(
            repo="akasper/empty-repo",
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
        client = Mock()
        ref_seen = {"count": 0}
        git_store: dict = {}

        def api_side(endpoint, *a, **k):
            endpoint = str(endpoint)
            method = k.get("method", "GET")
            if endpoint == "repos/akasper/empty-repo":
                return {"has_wiki": False, "default_branch": "main", "permissions": {"push": True}}
            if endpoint == "repos/akasper/empty-repo/git/ref/heads/main":
                ref_seen["count"] += 1
                if ref_seen["count"] < 2:
                    raise GhApiError("gh: Git Repository is empty. (HTTP 409)")
                return {"object": {"sha": "abc123"}}
            if endpoint == "repos/akasper/empty-repo/contents/README.md" and method == "PUT":
                return {"content": {"sha": "readme"}}
            if "/issues?" in endpoint and "labels=Question" in endpoint:
                return []
            if endpoint.startswith("repos/akasper/empty-repo/contents/"):
                if method == "GET":
                    raise GhApiError("gh: Not Found (HTTP 404)")
                return {}
            if endpoint == "repos/akasper/empty-repo/labels":
                return {}
            if endpoint == "repos/akasper/empty-repo/issues" and method == "POST":
                return {"number": 1}
            if endpoint == "repos/akasper/empty-repo/branches/main":
                return {"commit": {"sha": "abc123"}}
            if endpoint.startswith("repos/akasper/empty-repo/branches/"):
                raise GhApiError("HTTP 404")
            if endpoint == "repos/akasper/empty-repo/git/refs" and method == "POST":
                return {}
            git_resp = _bootstrap_git_data_side_effect(endpoint, method, git_store)
            if git_resp is not None:
                return git_resp
            return {}

        client.api.side_effect = api_side
        with _make_template_root() as tmpdir:
            template_root = Path(tmpdir)
            with patch(
                "plate_core.bootstrap.resolve_template_source",
                return_value=(template_root, "explicit_path"),
            ):
                report = run_bootstrap("akasper/empty-repo", apply_mode=True, client=client)

        readme_puts = [
            c
            for c in client.api.call_args_list
            if c.args and "contents/README.md" in str(c.args[0]) and c.kwargs.get("method") == "PUT"
        ]
        self.assertTrue(readme_puts, "Expected initial README commit when ref lookup returns 409 empty repo")
        self.assertEqual(ref_seen["count"], 3)

    @patch("plate_core.bootstrap.get_health")
    def test_apply_rerun_after_partial_run_skips_identical_and_finishes_steps(self, mock_get_health):
        """#1152: identical remote files are skipped; labels/.plate/questions/branches still run."""
        mock_get_health.return_value = HealthReport(
            repo="akasper/partial-repo",
            label_coverage_ok=False,
            missing_labels=["Feature", "Epic"],
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
        agents_text = prepare_copied_text("AGENTS.md", "# AGENTS\n", "posix", namespaced=False)
        agents_b64 = base64.b64encode(agents_text.encode("utf-8")).decode("ascii")
        client = Mock()
        git_store: dict = {}

        def api_side(endpoint, *a, **k):
            endpoint = str(endpoint)
            method = k.get("method", "GET")
            if endpoint == "repos/akasper/partial-repo":
                return {"has_wiki": False, "default_branch": "main", "permissions": {"push": True}}
            if endpoint == "repos/akasper/partial-repo/git/ref/heads/main":
                return {"object": {"sha": "abc123"}}
            if "/labels?" in endpoint:
                return []
            if endpoint == "repos/akasper/partial-repo/contents/AGENTS.md" and method == "GET":
                return {"content": agents_b64, "encoding": "base64"}
            if endpoint.startswith("repos/akasper/partial-repo/contents/"):
                if method == "GET":
                    raise GhApiError("gh: Not Found (HTTP 404)")
                return {}
            if endpoint == "repos/akasper/partial-repo/labels" and method == "POST":
                return {}
            if endpoint == "repos/akasper/partial-repo/issues" and method == "POST":
                return {"number": 42}
            if "/issues?" in endpoint and "labels=Question" in endpoint:
                return []
            if endpoint == "repos/akasper/partial-repo/branches/main":
                return {"commit": {"sha": "deadbeef"}}
            if endpoint.startswith("repos/akasper/partial-repo/branches/"):
                raise GhApiError("HTTP 404")
            if endpoint == "repos/akasper/partial-repo/git/refs" and method == "POST":
                return {}
            git_resp = _bootstrap_git_data_side_effect(endpoint, method, git_store, parent_commit="deadbeef")
            if git_resp is not None:
                return git_resp
            return {}

        client.api.side_effect = api_side
        with _make_template_root() as tmpdir:
            template_root = Path(tmpdir)
            _write_template_file(
                template_root,
                ".github/labels.yml",
                """
- name: Feature
  color: "0e8a16"
  description: "Issue type: feature."
- name: Epic
  color: "5319e7"
  description: "Issue type: epic."
""".strip()
                + "\n",
            )
            with tempfile.TemporaryDirectory() as empty_checkout:
                with patch(
                    "plate_core.bootstrap.resolve_template_source",
                    return_value=(template_root, "explicit_path"),
                ):
                    report = run_bootstrap(
                        "akasper/partial-repo",
                        apply_mode=True,
                        client=client,
                        local_root=empty_checkout,
                    )

        template_puts = [
            c
            for c in client.api.call_args_list
            if c.args
            and "repos/akasper/partial-repo/contents/" in str(c.args[0])
            and c.kwargs.get("method") == "PUT"
        ]
        put_paths = [str(c.args[0]) for c in template_puts]
        self.assertFalse(put_paths, "Grouped commit should not use per-file contents PUT")

        tree_posts = [
            c
            for c in client.api.call_args_list
            if c.args and str(c.args[0]).endswith("/git/trees") and c.kwargs.get("method") == "POST"
        ]
        self.assertTrue(tree_posts, "Expected grouped bootstrap tree write")
        tree_paths = {
            entry.get("path")
            for entry in tree_posts[0].kwargs.get("fields", {}).get("tree", [])
            if isinstance(entry, dict)
        }
        self.assertNotIn("AGENTS.md", tree_paths, "Identical AGENTS.md must not be re-uploaded")
        self.assertIn("docs/wiki/Goals.md", tree_paths, "Missing files should still upload")
        self.assertIn(".plate", tree_paths)

        label_posts = [
            c
            for c in client.api.call_args_list
            if c.args
            and c.args[0] == "repos/akasper/partial-repo/labels"
            and c.kwargs.get("method") == "POST"
        ]
        self.assertEqual(len(label_posts), 2)

        question_posts = [
            c
            for c in client.api.call_args_list
            if c.args
            and c.args[0] == "repos/akasper/partial-repo/issues"
            and c.kwargs.get("method") == "POST"
            and "Question" in str(c.kwargs.get("fields", {}).get("labels", []))
        ]
        self.assertEqual(len(question_posts), 3)

        plate_puts = [c for c in template_puts if ".plate" in str(c.args[0])]
        self.assertFalse(plate_puts, ".plate should be in grouped bootstrap commit, not contents PUT")

        branch_posts = [
            c
            for c in client.api.call_args_list
            if c.args and c.args[0] == "repos/akasper/partial-repo/git/refs" and c.kwargs.get("method") == "POST"
        ]
        self.assertEqual(len(branch_posts), 4, "Release track branches should be created")

        copy_action = next(a for a in report.actions if a.name == "copy-template-payload")
        self.assertEqual(copy_action.state, "applied")
        self.assertIn("skipped", copy_action.detail.lower())
        self.assertIn("AGENTS.md", copy_action.detail)

    def test_format_skipped_files_phrase_caps_list(self):
        from plate_core.bootstrap import _format_skipped_files_phrase

        paths = [f"path{i}.md" for i in range(25)]
        phrase = _format_skipped_files_phrase(paths)
        self.assertIn("skipped 25 existing files", phrase)
        self.assertIn("path0.md", phrase)
        self.assertIn("path19.md", phrase)
        self.assertNotIn("path20.md", phrase)
        self.assertIn("and 5 more", phrase)

        stale_phrase = _format_skipped_files_phrase(["AGENTS.md"], stale=True)
        self.assertIn("skipped but stale", stale_phrase)
        self.assertIn("AGENTS.md", stale_phrase)

    def test_remote_file_digest_empty_content(self):
        from plate_core.bootstrap import _remote_file_digest

        empty_hash = hashlib.sha256(b"").hexdigest()
        self.assertEqual(_remote_file_digest({"content": "", "encoding": "base64"}), empty_hash)
        self.assertIsNone(_remote_file_digest({"type": "file"}))
        self.assertIsNone(_remote_file_digest(None))

    @patch("plate_core.bootstrap.get_health")
    def test_empty_remote_agents_is_stale_when_template_nonempty(self, mock_get_health):
        """#1257: zero-byte remote file must not count as identical to bundled AGENTS.md."""
        mock_get_health.return_value = HealthReport(
            repo="akasper/empty-agents",
            label_coverage_ok=True,
            missing_labels=[],
            binary_artifacts_tracked=0,
            branch_protection_enabled=True,
            open_epic_count=1,
            status="pass",
            goals_page_present=True,
            open_question_count=0,
            plate_config_present=True,
            plate_config_valid=True,
            curiosity_answers_present=False,
        )
        client = Mock()
        git_store: dict = {}

        def api_side(endpoint, *a, **k):
            endpoint = str(endpoint)
            method = k.get("method", "GET")
            if endpoint == "repos/akasper/empty-agents":
                return {"has_wiki": True, "default_branch": "main", "permissions": {"push": True}}
            if endpoint == "repos/akasper/empty-agents/git/ref/heads/main":
                return {"object": {"sha": "abc123"}}
            if endpoint == "repos/akasper/empty-agents/contents/AGENTS.md" and method == "GET":
                return {"content": "", "encoding": "base64"}
            if endpoint.startswith("repos/akasper/empty-agents/contents/"):
                if method == "GET":
                    raise GhApiError("gh: Not Found (HTTP 404)")
                return {}
            if "/issues?" in endpoint and "labels=Question" in endpoint:
                return []
            if "/issues?" in endpoint and "labels=Epic" in endpoint:
                return [{"number": 1}]
            if endpoint.startswith("repos/akasper/empty-agents/branches/"):
                return {"commit": {"sha": "abc"}}
            git_resp = _bootstrap_git_data_side_effect(endpoint, method, git_store)
            if git_resp is not None:
                return git_resp
            return {}

        client.api.side_effect = api_side
        with _make_template_root() as tmpdir:
            template_root = Path(tmpdir)
            with patch(
                "plate_core.bootstrap.resolve_template_source",
                return_value=(template_root, "explicit_path"),
            ):
                report = run_bootstrap("akasper/empty-agents", apply_mode=True, client=client)

        copy_action = next(a for a in report.actions if a.name == "copy-template-payload")
        self.assertIn("skipped but stale", copy_action.detail)
        self.assertIn("AGENTS.md", copy_action.detail)
        self.assertIn("self-migrate --plan", copy_action.detail)

    @patch("plate_core.bootstrap.get_health")
    def test_apply_reports_stale_and_identical_skips_separately(self, mock_get_health):
        """#1257: differing remote payload files are skipped-but-stale, not plain skipped."""
        mock_get_health.return_value = HealthReport(
            repo="akasper/stale-repo",
            label_coverage_ok=True,
            missing_labels=[],
            binary_artifacts_tracked=0,
            branch_protection_enabled=True,
            open_epic_count=1,
            status="pass",
            goals_page_present=True,
            open_question_count=0,
            plate_config_present=True,
            plate_config_valid=True,
            curiosity_answers_present=False,
        )
        agents_text = prepare_copied_text("AGENTS.md", "# AGENTS\n", "posix", namespaced=False)
        readme_text = prepare_copied_text("README.md", "# README\n", "posix", namespaced=False)
        stale_b64 = base64.b64encode(b"# OLD AGENTS\n").decode("ascii")
        readme_b64 = base64.b64encode(readme_text.encode("utf-8")).decode("ascii")
        client = Mock()
        git_store: dict = {}

        def api_side(endpoint, *a, **k):
            endpoint = str(endpoint)
            method = k.get("method", "GET")
            if endpoint == "repos/akasper/stale-repo":
                return {"has_wiki": True, "default_branch": "main", "permissions": {"push": True}}
            if endpoint == "repos/akasper/stale-repo/git/ref/heads/main":
                return {"object": {"sha": "abc123"}}
            if endpoint == "repos/akasper/stale-repo/contents/AGENTS.md" and method == "GET":
                return {"content": stale_b64, "encoding": "base64"}
            if endpoint == "repos/akasper/stale-repo/contents/README.md" and method == "GET":
                return {"content": readme_b64, "encoding": "base64"}
            if endpoint.startswith("repos/akasper/stale-repo/contents/"):
                if method == "GET":
                    raise GhApiError("gh: Not Found (HTTP 404)")
                return {}
            if "/issues?" in endpoint and "labels=Question" in endpoint:
                return []
            if "/issues?" in endpoint and "labels=Epic" in endpoint:
                return [{"number": 1}]
            if endpoint.startswith("repos/akasper/stale-repo/branches/"):
                return {"commit": {"sha": "abc"}}
            git_resp = _bootstrap_git_data_side_effect(endpoint, method, git_store)
            if git_resp is not None:
                return git_resp
            return {}

        client.api.side_effect = api_side
        with _make_template_root() as tmpdir:
            template_root = Path(tmpdir)
            with patch(
                "plate_core.bootstrap.resolve_template_source",
                return_value=(template_root, "explicit_path"),
            ):
                report = run_bootstrap("akasper/stale-repo", apply_mode=True, client=client)

        copy_action = next(a for a in report.actions if a.name == "copy-template-payload")
        self.assertIn("skipped but stale", copy_action.detail)
        self.assertIn("AGENTS.md", copy_action.detail)
        self.assertIn("skipped 1 existing file (README.md)", copy_action.detail)
        self.assertNotIn("README.md)", copy_action.detail.split("skipped but stale")[1])
        self.assertIn("self-migrate --plan", copy_action.detail)
        self.assertTrue(any("self-migrate --plan" in s for s in report.next_steps))

        template_puts = [
            c
            for c in client.api.call_args_list
            if c.args
            and "repos/akasper/stale-repo/contents/" in str(c.args[0])
            and c.kwargs.get("method") == "PUT"
        ]
        put_paths = [str(c.args[0]) for c in template_puts]
        self.assertFalse(any("AGENTS.md" in p for p in put_paths))
        self.assertFalse(any("README.md" in p for p in put_paths))

    @patch("plate_core.bootstrap.get_health")
    def test_apply_wraps_contents_404_with_repo_branch_path_context(self, mock_get_health):
        mock_get_health.return_value = HealthReport(
            repo="akasper/test-repo",
            label_coverage_ok=True,
            missing_labels=[],
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
        client = Mock()
        git_store: dict = {}

        def api_side(endpoint, *a, **k):
            endpoint = str(endpoint)
            method = k.get("method", "GET")
            if endpoint == "repos/akasper/test-repo":
                return {"has_wiki": False, "default_branch": "main", "permissions": {"push": True}}
            if endpoint == "repos/akasper/test-repo/git/ref/heads/main":
                return {"object": {"sha": "abc123"}}
            if "/issues?" in endpoint and "labels=Question" in endpoint:
                return []
            if endpoint.startswith("repos/akasper/test-repo/contents/"):
                if method == "GET":
                    raise GhApiError("gh: Not Found (HTTP 404)")
                raise GhApiError("gh: Not Found (HTTP 404)")
            if method == "POST" and endpoint.endswith("/git/blobs"):
                raise GhApiError("gh: Not Found (HTTP 404)")
            git_resp = _bootstrap_git_data_side_effect(endpoint, method, git_store)
            if git_resp is not None:
                return git_resp
            return {}

        client.api.side_effect = api_side
        with _make_template_root() as tmpdir:
            template_root = Path(tmpdir)
            with patch(
                "plate_core.bootstrap.resolve_template_source",
                return_value=(template_root, "explicit_path"),
            ):
                with self.assertRaises(RuntimeError) as ctx:
                    run_bootstrap("akasper/test-repo", apply_mode=True, client=client)
        msg = str(ctx.exception)
        self.assertIn("repo=akasper/test-repo", msg)
        self.assertIn("branch=main", msg)
        self.assertIn("path=AGENTS.md", msg)
        self.assertIn("404", msg.lower())

    @patch("plate_core.bootstrap.get_health")
    def test_apply_groups_template_payload_into_one_git_commit(self, mock_get_health):
        """#1277: greenfield apply should not create one contents API commit per template file."""
        mock_get_health.return_value = HealthReport(
            repo="akasper/grouped-repo",
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

        def api_side(endpoint, *a, **k):
            endpoint = str(endpoint)
            method = k.get("method", "GET")
            if endpoint == "repos/akasper/grouped-repo":
                return {"has_wiki": True, "default_branch": "main", "permissions": {"push": True}}
            if "/issues?" in endpoint and "labels=Question" in endpoint:
                return []
            if endpoint.startswith("repos/akasper/grouped-repo/contents/"):
                if "README.md" in endpoint and method == "GET":
                    return {"type": "file"}
                if method == "GET":
                    raise GhApiError("HTTP 404 Not Found")
                return {}
            if endpoint.startswith("repos/akasper/grouped-repo/branches/main"):
                return {"commit": {"sha": "abc123"}}
            if endpoint.startswith("repos/akasper/grouped-repo/branches/"):
                raise GhApiError("HTTP 404 Not Found")
            if endpoint == "repos/akasper/grouped-repo/git/refs" and method == "POST":
                return {}
            git_resp = _bootstrap_git_data_side_effect(endpoint, method, git_store)
            if git_resp is not None:
                return git_resp
            return {}

        client.api.side_effect = api_side
        with _make_template_root() as tmpdir:
            template_root = Path(tmpdir)
            with patch(
                "plate_core.bootstrap.resolve_template_source",
                return_value=(template_root, "explicit_path"),
            ):
                run_bootstrap("akasper/grouped-repo", apply_mode=True, client=client)

        contents_puts = [
            c
            for c in client.api.call_args_list
            if c.args
            and "repos/akasper/grouped-repo/contents/" in str(c.args[0])
            and c.kwargs.get("method") == "PUT"
        ]
        self.assertFalse(contents_puts)
        commit_posts = [
            c
            for c in client.api.call_args_list
            if c.args
            and str(c.args[0]).endswith("/git/commits")
            and c.kwargs.get("method") == "POST"
        ]
        self.assertEqual(commit_posts[0].kwargs.get("fields", {}).get("message"), "Bootstrap: initialize PLATE template payload")
        self.assertEqual(len(commit_posts), 1)
        self.assertGreaterEqual(git_store.get("blob_count", 0), 2)


if __name__ == "__main__":
    unittest.main()
