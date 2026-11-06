"""Contract tests for issue lifecycle policy slice (#1425) — pure / shadow only."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
import textwrap
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import yaml

from plate_core.cli import main
from plate_core.lifecycle_policy import (
    DEFAULT_LIFECYCLE_GATES,
    assert_no_path_removes_human_review,
    decide_approval_command,
    decide_issue_label_change,
    label_change_is_approver_only_downgrade,
    effective_tier_authority,
    gate_requires_human_review,
    match_labels_by_taxonomy,
    merged_lifecycle_gates,
    parse_lifecycle_approvers_list,
    parse_pending_write_record,
    plan_init_process_yaml,
    pl_allowed_code_paths_for_human_review_audit,
    read_process_yaml_root,
    resolve_runtime_approvers,
    RollingCriticalRaiseTracker,
    stricter_autonomy_cap,
)

_MINIMAL_PROCESS_ROOT = {
    "labels": {
        "issue_type_labels": {
            "required_exactly_one": [
                "Bug",
                "Feature",
                "Epic",
                "Release",
                "Research",
                "Design",
                "Question",
                "Task",
                "Audit",
                "Migration",
            ]
        },
        "prefix_convention": {"area": "area:", "risk": "risk:", "need": "need:"},
    }
}


class InitProcessYamlTests(unittest.TestCase):
    def test_init_writes_approvers_from_token_user_repo(self):
        fragment = plan_init_process_yaml(
            token_user_login="alice",
            repo_obj={"owner": {"type": "User", "login": "alice"}},
            org_approvers=None,
            process_yaml_root=_MINIMAL_PROCESS_ROOT,
        )
        self.assertEqual(fragment["lifecycle"]["approvers"], ["alice"])
        self.assertIn("merge", fragment["lifecycle"]["gates"])
        self.assertTrue(fragment["lifecycle"]["gates"]["merge"])
        self.assertIn("type_labels", fragment["lifecycle"]["taxonomy"])

    def test_init_requires_approvers_for_org_repo(self):
        with self.assertRaises(ValueError) as ctx:
            plan_init_process_yaml(
                token_user_login="alice",
                repo_obj={"owner": {"type": "Organization", "login": "acme"}},
                org_approvers=None,
                process_yaml_root=_MINIMAL_PROCESS_ROOT,
            )
        self.assertIn("explicit approvers", str(ctx.exception).lower())

        frag = plan_init_process_yaml(
            token_user_login="alice",
            repo_obj={"owner": {"type": "Organization", "login": "acme"}},
            org_approvers=["bob", "carol"],
            process_yaml_root=_MINIMAL_PROCESS_ROOT,
        )
        self.assertEqual(list(frag["lifecycle"]["approvers"]), ["bob", "carol"])


class RuntimeApproverTests(unittest.TestCase):
    def test_runtime_fallback_owner_only_for_user_repo(self):
        r = resolve_runtime_approvers(
            lifecycle_block={},
            lifecycle_parse_error=None,
            repo_obj={"owner": {"type": "User", "login": "dana"}},
        )
        self.assertFalse(r.refuse_all)
        self.assertEqual(r.logins, ("dana",))
        self.assertEqual(r.source, "owner_fallback")

    def test_explicit_null_approvers_fail_closed(self):
        r = resolve_runtime_approvers(
            lifecycle_block={"approvers": None},
            lifecycle_parse_error=None,
            repo_obj={"owner": {"type": "User", "login": "dana"}},
        )
        self.assertTrue(r.refuse_all)
        self.assertIn("null", r.reason.lower())

    def test_malformed_lifecycle_fail_closed(self):
        r = resolve_runtime_approvers(
            lifecycle_block=None,
            lifecycle_parse_error="lifecycle must be a mapping",
            repo_obj={"owner": {"type": "User", "login": "dana"}},
        )
        self.assertTrue(r.refuse_all)

    def test_empty_approvers_refuses_approval_actions(self):
        r = resolve_runtime_approvers(
            lifecycle_block={"approvers": []},
            lifecycle_parse_error=None,
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
            lifecycle_block={"approvers": ["boss"]},
            lifecycle_parse_error=None,
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
            process_yaml_root=_MINIMAL_PROCESS_ROOT,
        )
        self.assertFalse(dec.allowed)
        self.assertEqual(dec.kind, "downgrade_reverted")

    def test_tier_downgrade_blocked(self):
        down, reasons = label_change_is_approver_only_downgrade(
            ["tier:T3", "Feature"],
            ["tier:T2", "Feature"],
            process_yaml_root=_MINIMAL_PROCESS_ROOT,
        )
        self.assertTrue(down)
        self.assertTrue(any("tier_downgrade" in x for x in reasons))

    def test_tier_downgrade_renamed_taxonomy(self):
        life = {
            "taxonomy": {
                "type_labels": "labels.issue_type_labels",
                "prefixes": "labels.prefix_convention",
                "tier_prefix": "level:",
            }
        }
        down, reasons = label_change_is_approver_only_downgrade(
            ["level:T3", "Feature"],
            ["level:T2", "Feature"],
            process_yaml_root=_MINIMAL_PROCESS_ROOT,
            lifecycle_block=life,
        )
        self.assertTrue(down)
        self.assertTrue(any("tier_downgrade" in x for x in reasons))
        self.assertEqual(
            effective_tier_authority(["level:T3"], process_yaml_root=_MINIMAL_PROCESS_ROOT, lifecycle_block=life),
            "T3",
        )

    def test_replace_low_with_critical_is_not_downgrade(self):
        down, reasons = label_change_is_approver_only_downgrade(
            ["risk:low", "Feature"],
            ["risk:critical", "Feature"],
            process_yaml_root=_MINIMAL_PROCESS_ROOT,
        )
        self.assertFalse(down, msg=reasons)

    def test_fourth_critical_raise_in_hour_reverted(self):
        resolved = resolve_runtime_approvers(
            lifecycle_block={"approvers": ["boss"]},
            lifecycle_parse_error=None,
            repo_obj={"owner": {"type": "User", "login": "boss"}},
        )
        tracker = RollingCriticalRaiseTracker(window=timedelta(hours=1))
        t0 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
        prev_sets = [
            (["risk:low"], ["risk:critical"]),
            (["risk:medium"], ["risk:critical"]),
            (["risk:high"], ["risk:critical"]),
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
                process_yaml_root=_MINIMAL_PROCESS_ROOT,
            )
            self.assertTrue(dec.allowed, msg=f"iteration {i}")
        dec4 = decide_issue_label_change(
            prev_labels=["risk:low"],
            new_labels=["risk:critical"],
            actor_login=actor,
            resolved=resolved,
            critical_tracker=tracker,
            now=t0 + timedelta(minutes=10),
            process_yaml_root=_MINIMAL_PROCESS_ROOT,
        )
        self.assertFalse(dec4.allowed)
        self.assertEqual(dec4.kind, "critical_raise_rate_limited")

    def test_command_parsed_from_first_line_only(self):
        resolved = resolve_runtime_approvers(
            lifecycle_block={"approvers": ["pat"]},
            lifecycle_parse_error=None,
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

    def test_pending_write_blocks_on_structured_record(self):
        resolved = resolve_runtime_approvers(
            lifecycle_block={"approvers": ["pat"]},
            lifecycle_parse_error=None,
            repo_obj={"owner": {"type": "User", "login": "pat"}},
        )
        rec = json.dumps(
            {"transition_id": "t1", "added": ["risk:low"], "removed": []}
        )
        d = decide_approval_command(
            comment_body="/plate approve",
            actor_login="pat",
            resolved=resolved,
            pending_write_record_json=rec,
        )
        self.assertFalse(d.allowed)
        self.assertEqual(d.kind, "pending_write")

    def test_parse_pending_write_record_strict(self):
        self.assertIsNone(parse_pending_write_record('{"transition_id": ""}'))
        self.assertIsNotNone(
            parse_pending_write_record(
                '{"transition_id":"x","added":["a"],"removed":[]}'
            )
        )


class PolicyPrimitiveTests(unittest.TestCase):
    def test_gate_semantics_true_means_human_required(self):
        gates = merged_lifecycle_gates(None)
        self.assertTrue(gate_requires_human_review("merge", gates))
        self.assertFalse(gate_requires_human_review("merge", {"merge": False}))
        self.assertTrue(gate_requires_human_review("gate_label_downgrade", {"gate_label_downgrade": False}))

    def test_taxonomy_attribute_matching(self):
        labels = ["risk:critical", "tier:T3", "Feature"]
        m = match_labels_by_taxonomy(
            labels,
            risk="critical",
            tier="T3",
            issue_type="Feature",
            process_yaml_root=_MINIMAL_PROCESS_ROOT,
        )
        self.assertTrue(m.ok)
        m2 = match_labels_by_taxonomy(
            labels, risk="high", process_yaml_root=_MINIMAL_PROCESS_ROOT
        )
        self.assertFalse(m2.ok)

    def test_stricter_of_gate_and_risk_tolerance(self):
        ok, reason = stricter_autonomy_cap(
            gate_requires_human=True,
            risk_tolerance="low",
            action_needs_min_tolerance="medium",
        )
        self.assertFalse(ok)
        self.assertIn("lifecycle gate", reason.lower())

    def test_parse_approvers_errors_on_wrong_type(self):
        with self.assertRaises(ValueError):
            parse_lifecycle_approvers_list("alice")

    def test_process_yaml_non_mapping_root_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".agentic").mkdir(parents=True, exist_ok=True)
            (root / ".agentic" / "process.yml").write_text("- not a mapping\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                read_process_yaml_root(root)


class HumanReviewSourceScanTests(unittest.TestCase):
    def test_no_code_path_removes_human_review(self):
        assert_no_path_removes_human_review(pl_allowed_code_paths_for_human_review_audit())


class ProcessInitCliTests(unittest.TestCase):
    def _minimal_process_yaml(self) -> str:
        return textwrap.dedent(
            """\
            labels:
              issue_type_labels:
                required_exactly_one:
                  - Bug
                  - Feature
                  - Epic
                  - Release
                  - Research
                  - Design
                  - Question
                  - Task
                  - Audit
                  - Migration
              prefix_convention:
                area: "area:"
                risk: "risk:"
                need: "need:"
            """
        )

    def test_process_init_writes_file_mocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            mock_repo = {"owner": {"type": "User", "login": "alice"}}
            (root / ".agentic").mkdir(parents=True, exist_ok=True)
            (root / ".agentic" / "process.yml").write_text(
                self._minimal_process_yaml(), encoding="utf-8"
            )
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
            self.assertEqual(
                data["lifecycle"]["taxonomy"]["type_labels"],
                "labels.issue_type_labels",
            )

    def test_process_init_merge_preserves_process_root_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".agentic").mkdir(parents=True, exist_ok=True)
            merged = yaml.safe_dump(
                {
                    "process": {"name": "X", "version": "0.1"},
                    "labels": _MINIMAL_PROCESS_ROOT["labels"],
                }
            )
            (root / ".agentic" / "process.yml").write_text(merged, encoding="utf-8")
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

    def test_rerun_init_preserves_stricter_gates_and_approvers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".agentic").mkdir(parents=True, exist_ok=True)
            strict_gates = dict(DEFAULT_LIFECYCLE_GATES)
            strict_gates["merge"] = True
            strict_gates["start"] = True
            doc = {"labels": _MINIMAL_PROCESS_ROOT["labels"]}
            doc["lifecycle"] = {
                "approvers": ["bob", "carol"],
                "gates": strict_gates,
            }
            (root / ".agentic" / "process.yml").write_text(
                yaml.safe_dump(doc), encoding="utf-8"
            )
            mock_repo = {"owner": {"type": "User", "login": "alice"}}
            with (
                patch("plate_core.cli.resolve_repo", return_value="alice/plate"),
                patch("plate_core.cli.fetch_token_user_login", return_value="intruder"),
                patch("plate_core.cli.fetch_repo", return_value=mock_repo),
            ):
                code = main(["process", "init", "--repo-root", str(root), "--json"])
            self.assertEqual(code, 0)
            data = yaml.safe_load((root / ".agentic" / "process.yml").read_text(encoding="utf-8"))
            self.assertEqual(data["lifecycle"]["approvers"], ["bob", "carol"])
            self.assertTrue(data["lifecycle"]["gates"]["merge"])
            self.assertTrue(data["lifecycle"]["gates"]["start"])

    def test_init_preserves_explicit_empty_approvers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".agentic").mkdir(parents=True, exist_ok=True)
            doc = {"labels": _MINIMAL_PROCESS_ROOT["labels"]}
            doc["lifecycle"] = {"approvers": [], "gates": {"merge": True}}
            (root / ".agentic" / "process.yml").write_text(
                yaml.safe_dump(doc), encoding="utf-8"
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
            self.assertEqual(data["lifecycle"]["approvers"], [])

    def test_init_rejects_explicit_null_approvers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".agentic").mkdir(parents=True, exist_ok=True)
            raw = (
                self._minimal_process_yaml()
                + "\nlifecycle:\n  approvers: null\n  gates: {}\n"
            )
            (root / ".agentic" / "process.yml").write_text(raw, encoding="utf-8")
            mock_repo = {"owner": {"type": "User", "login": "alice"}}
            with (
                patch("plate_core.cli.resolve_repo", return_value="alice/plate"),
                patch("plate_core.cli.fetch_token_user_login", return_value="alice"),
                patch("plate_core.cli.fetch_repo", return_value=mock_repo),
            ):
                code = main(["process", "init", "--repo-root", str(root), "--json"])
            self.assertEqual(code, 1)

    def test_explicit_approvers_non_owner_requires_confirm(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".agentic").mkdir(parents=True, exist_ok=True)
            (root / ".agentic" / "process.yml").write_text(
                self._minimal_process_yaml(), encoding="utf-8"
            )
            mock_repo = {"owner": {"type": "User", "login": "alice"}}
            with (
                patch("plate_core.cli.resolve_repo", return_value="alice/plate"),
                patch("plate_core.cli.fetch_token_user_login", return_value="bob"),
                patch("plate_core.cli.fetch_repo", return_value=mock_repo),
            ):
                code = main(
                    [
                        "process",
                        "init",
                        "--repo-root",
                        str(root),
                        "--approvers",
                        "carol",
                        "--json",
                    ]
                )
            self.assertEqual(code, 1)

    def test_invalid_process_yml_root_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".agentic").mkdir(parents=True, exist_ok=True)
            (root / ".agentic" / "process.yml").write_text("bad: [", encoding="utf-8")
            mock_repo = {"owner": {"type": "User", "login": "alice"}}
            with (
                patch("plate_core.cli.resolve_repo", return_value="alice/plate"),
                patch("plate_core.cli.fetch_token_user_login", return_value="alice"),
                patch("plate_core.cli.fetch_repo", return_value=mock_repo),
            ):
                code = main(["process", "init", "--repo-root", str(root), "--json"])
            self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
