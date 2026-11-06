"""Contract tests for issue lifecycle policy slice (#1425) — pure / shadow only."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import yaml

from plate_core.cli import main
from plate_core.lifecycle_policy import (
    assert_no_path_removes_human_review,
    decide_approval_command,
    decide_issue_label_change,
    gate_requires_human_review,
    match_labels_by_taxonomy,
    merged_lifecycle_gates,
    parse_lifecycle_approvers_list,
    plan_init_process_yaml,
    pl_allowed_code_paths_for_human_review_audit,
    resolve_runtime_approvers,
    RollingCriticalRaiseTracker,
    stricter_autonomy_cap,
)


class InitProcessYamlTests(unittest.TestCase):
    def test_init_writes_approvers_from_token_user_repo(self):
        fragment = plan_init_process_yaml(
            token_user_login="alice",
            repo_obj={"owner": {"type": "User", "login": "alice"}},
            org_approvers=None,
        )
        self.assertEqual(fragment["lifecycle"]["approvers"], ["alice"])
        self.assertIn("merge", fragment["lifecycle"]["gates"])
        self.assertTrue(fragment["lifecycle"]["gates"]["merge"])

    def test_init_requires_approvers_for_org_repo(self):
        with self.assertRaises(ValueError) as ctx:
            plan_init_process_yaml(
                token_user_login="alice",
                repo_obj={"owner": {"type": "Organization", "login": "acme"}},
                org_approvers=None,
            )
        self.assertIn("explicit approvers", str(ctx.exception).lower())

        frag = plan_init_process_yaml(
            token_user_login="alice",
            repo_obj={"owner": {"type": "Organization", "login": "acme"}},
            org_approvers=["bob", "carol"],
        )
        self.assertEqual(list(frag["lifecycle"]["approvers"]), ["bob", "carol"])


class RuntimeApproverTests(unittest.TestCase):
    def test_runtime_fallback_owner_only_for_user_repo(self):
        r = resolve_runtime_approvers(
            lifecycle_yaml={},
            token_user_login="ignored",
            repo_obj={"owner": {"type": "User", "login": "dana"}},
        )
        self.assertFalse(r.refuse_all)
        self.assertEqual(r.logins, ("dana",))
        self.assertEqual(r.source, "owner_fallback")

    def test_empty_approvers_refuses_approval_actions(self):
        r = resolve_runtime_approvers(
            lifecycle_yaml={"approvers": []},
            token_user_login="x",
            repo_obj={"owner": {"type": "User", "login": "x"}},
        )
        self.assertTrue(r.refuse_all)
        d = decide_approval_command(
            comment_body="/plate approve\nextra",
            actor_login="x",
            resolved=r,
        )
        self.assertFalse(d.allowed)
        self.assertEqual(d.kind, "approver_required")


class ShadowDecisionTests(unittest.TestCase):
    def test_non_approver_downgrade_reverted(self):
        resolved = resolve_runtime_approvers(
            lifecycle_yaml={"approvers": ["boss"]},
            token_user_login=None,
            repo_obj={"owner": {"type": "User", "login": "boss"}},
        )
        prev = ["risk:high", "tier:T2"]
        new = ["tier:T2"]
        dec = decide_issue_label_change(
            prev_labels=prev,
            new_labels=new,
            actor_login="random",
            resolved=resolved,
            critical_tracker=None,
        )
        self.assertFalse(dec.allowed)
        self.assertEqual(dec.kind, "downgrade_reverted")

    def test_fourth_critical_raise_in_hour_reverted(self):
        resolved = resolve_runtime_approvers(
            lifecycle_yaml={"approvers": ["boss"]},
            token_user_login=None,
            repo_obj={"owner": {"type": "User", "login": "boss"}},
        )
        tracker = RollingCriticalRaiseTracker(window=timedelta(hours=1))
        t0 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
        prev_sets = [
            (["risk:low"], ["risk:low", "risk:critical"]),
            (["risk:medium"], ["risk:medium", "risk:critical"]),
            (["risk:high"], ["risk:high", "risk:critical"]),
        ]
        actor = "novice"
        for i, (p, n) in enumerate(prev_sets):
            dec = decide_issue_label_change(
                prev_labels=p,
                new_labels=n,
                actor_login=actor,
                resolved=resolved,
                critical_tracker=tracker,
                now=t0 + timedelta(minutes=i),
            )
            self.assertTrue(dec.allowed, msg=f"iteration {i}")
        dec4 = decide_issue_label_change(
            prev_labels=["risk:low"],
            new_labels=["risk:low", "risk:critical"],
            actor_login=actor,
            resolved=resolved,
            critical_tracker=tracker,
            now=t0 + timedelta(minutes=10),
        )
        self.assertFalse(dec4.allowed)
        self.assertEqual(dec4.kind, "critical_raise_rate_limited")

    def test_command_parsed_from_first_line_only(self):
        resolved = resolve_runtime_approvers(
            lifecycle_yaml={"approvers": ["pat"]},
            token_user_login=None,
            repo_obj={"owner": {"type": "User", "login": "pat"}},
        )
        body = "context line\n/plate approve"
        d = decide_approval_command(comment_body=body, actor_login="pat", resolved=resolved)
        self.assertFalse(d.allowed)
        self.assertEqual(d.kind, "not_approval_command")

        d2 = decide_approval_command(
            comment_body="/plate approve\nmore",
            actor_login="pat",
            resolved=resolved,
        )
        self.assertTrue(d2.allowed)

        d3 = decide_approval_command(
            comment_body="/plate approve\npending_write token PLATE_PENDING_WRITE",
            actor_login="pat",
            resolved=resolved,
        )
        self.assertFalse(d3.allowed)
        self.assertEqual(d3.kind, "pending_write")


class PolicyPrimitiveTests(unittest.TestCase):
    def test_gate_defaults_immutable_human_keys(self):
        gates = merged_lifecycle_gates(None)
        self.assertTrue(gate_requires_human_review("gate_label_downgrade", gates))
        self.assertTrue(gate_requires_human_review("merge", {"merge": False}))

    def test_taxonomy_attribute_matching(self):
        labels = ["risk:critical", "tier:T3", "Feature"]
        self.assertTrue(
            match_labels_by_taxonomy(labels, risk="critical", tier="T3", issue_type="Feature")
        )
        self.assertFalse(match_labels_by_taxonomy(labels, risk="high"))

    def test_stricter_of_gate_and_risk_tolerance(self):
        ok, reason = stricter_autonomy_cap(
            gate_allows=True,
            risk_tolerance="low",
            action_needs_min_tolerance="medium",
        )
        self.assertFalse(ok)
        self.assertIn("risk_tolerance", reason)

    def test_parse_approvers_errors_on_wrong_type(self):
        with self.assertRaises(ValueError):
            parse_lifecycle_approvers_list("alice")


class HumanReviewSourceScanTests(unittest.TestCase):
    def test_no_code_path_removes_human_review(self):
        assert_no_path_removes_human_review(pl_allowed_code_paths_for_human_review_audit())


class ProcessInitCliTests(unittest.TestCase):
    def test_process_init_writes_file_mocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            mock_repo = {"owner": {"type": "User", "login": "alice"}}
            out = io.StringIO()
            with (
                patch("plate_core.cli.resolve_repo", return_value="alice/plate"),
                patch("plate_core.cli.fetch_token_user_login", return_value="alice"),
                patch("plate_core.cli.fetch_repo", return_value=mock_repo),
                redirect_stdout(out),
            ):
                code = main(["process", "init", "--repo-root", str(root), "--json"])
            self.assertEqual(code, 0)
            payload = json.loads(out.getvalue().strip())
            self.assertTrue(payload.get("ok"))
            proc = root / ".agentic" / "process.yml"
            self.assertTrue(proc.is_file())
            data = yaml.safe_load(proc.read_text(encoding="utf-8"))
            self.assertEqual(data["lifecycle"]["approvers"], ["alice"])
            self.assertTrue(data["lifecycle"]["gates"]["merge"])

    def test_process_init_merge_preserves_process_root_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".agentic").mkdir(parents=True, exist_ok=True)
            (root / ".agentic" / "process.yml").write_text(
                yaml.safe_dump({"process": {"name": "X", "version": "0.1"}}),
                encoding="utf-8",
            )
            mock_repo = {"owner": {"type": "User", "login": "alice"}}
            with (
                patch("plate_core.cli.resolve_repo", return_value="alice/plate"),
                patch("plate_core.cli.fetch_token_user_login", return_value="alice"),
                patch("plate_core.cli.fetch_repo", return_value=mock_repo),
            ):
                code = main(["process", "init", "--repo-root", str(root), "--json"])
            self.assertEqual(code, 0)
            data = yaml.safe_load((root / ".agentic" / "process.yml").read_text(encoding="utf-8"))
            self.assertEqual(data["process"]["name"], "X")
            self.assertEqual(data["lifecycle"]["approvers"], ["alice"])


if __name__ == "__main__":
    unittest.main()
