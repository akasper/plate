"""Regression tests for auto-merge workflow eligibility (#1471)."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATHS = (
    REPO_ROOT / ".github" / "workflows" / "auto-merge.yml",
    REPO_ROOT
    / "src"
    / "plate_core"
    / "template_payload"
    / ".github"
    / "workflows"
    / "auto-merge.yml",
)
LEGACY_MARKER = ".github/AUTONOMOUS_MODE"
INVENTORY = REPO_ROOT / "src" / "plate_core" / "data" / "template_payload_inventory.json"


def read_workflow() -> str:
    texts = [p.read_text(encoding="utf-8") for p in WORKFLOW_PATHS]
    if texts[0] != texts[1]:
        raise AssertionError("auto-merge.yml drift: repo root != template payload")
    return texts[0]


def extract_check_script(workflow_text: str) -> str:
    name_line = "- name: Check .plate autonomy and PR eligibility"
    if name_line not in workflow_text:
        raise AssertionError("missing eligibility check step")
    start = workflow_text.index(name_line)
    script_idx = workflow_text.index("script: |", start)
    lines: list[str] = []
    for line in workflow_text[script_idx:].splitlines()[1:]:
        if line.startswith("            "):
            lines.append(line[12:])
        elif not line.strip():
            lines.append("")
        else:
            break
    body = "\n".join(lines).strip()
    if not body:
        raise AssertionError("eligibility github-script body is empty")
    return body


# Mirrors resolveAutonomy / pathBlocked / prRiskAllowed in auto-merge.yml (stdlib only).
RISK_RANK = {"low": 1, "medium": 2, "high": 3, "critical": 4}
DENY_EXACT = frozenset(
    {"AGENTS.md", "SPEC.md", ".github/CODEOWNERS", "README.md", ".plate"}
)
DENY_PREFIXES = (".github/workflows/",)
BLOCKED_NEED = frozenset({"need:human-review", "need:security-review"})


def path_blocked(filename: str) -> bool:
    if not filename:
        return False
    if filename in DENY_EXACT:
        return True
    return any(filename.startswith(p) for p in DENY_PREFIXES)


def resolve_autonomy(
    plate: dict | None, has_legacy_marker: bool, plate_file_present: bool
) -> dict:
    has_section = (
        plate
        and isinstance(plate.get("autonomy"), dict)
        and not isinstance(plate.get("autonomy"), list)
    )
    if plate_file_present and not has_section:
        return {"active": False, "tolerance": "off", "source": "plate"}
    if has_section:
        aut = plate["autonomy"]
        enabled = aut.get("enabled") is True
        tolerance = str(aut.get("risk_tolerance") or "off").lower()
        if not enabled or tolerance == "off":
            return {"active": False, "tolerance": tolerance, "source": "plate"}
        return {"active": True, "tolerance": tolerance, "source": "plate"}
    if has_legacy_marker:
        return {"active": True, "tolerance": "low", "source": "legacy_marker"}
    return {"active": False, "tolerance": "off", "source": "none"}


def pr_risk_allowed(pr_risk_label: str, tolerance: str) -> bool:
    pr_level = pr_risk_label.lower().replace("risk:", "")
    if pr_level not in RISK_RANK or pr_level == "critical":
        return False
    tol_rank = RISK_RANK.get(tolerance, 0)
    return tol_rank >= RISK_RANK[pr_level]


def evaluate_pr(
    *,
    plate: dict | None,
    has_legacy_marker: bool,
    plate_file_present: bool = False,
    risk_labels: list[str],
    need_labels: list[str],
    changed_files: list[str],
) -> bool:
    mode = resolve_autonomy(plate, has_legacy_marker, plate_file_present)
    if not mode["active"]:
        return False
    if any(n.lower() in BLOCKED_NEED for n in need_labels):
        return False
    if len(risk_labels) != 1 or not pr_risk_allowed(risk_labels[0], mode["tolerance"]):
        return False
    if any(path_blocked(f) for f in changed_files):
        return False
    return True


class AutoMergeWorkflowTests(unittest.TestCase):
    def test_workflows_in_sync_and_read_plate(self):
        workflow = read_workflow()
        self.assertIn("path: '.plate'", workflow)
        self.assertIn("resolveAutonomy", workflow)
        self.assertIn("need:human-review", workflow)
        self.assertIn("listFiles", workflow)
        self.assertIn("auto-merge-enable:", workflow)
        self.assertRegex(workflow, r"auto-merge-enable:[\s\S]*contents: write")

    def test_marker_not_shipped_in_repo_or_inventory(self):
        for rel in (
            LEGACY_MARKER,
            f"src/plate_core/template_payload/{LEGACY_MARKER}",
        ):
            self.assertFalse((REPO_ROOT / rel).is_file(), f"{rel} should be removed")
        inventory = INVENTORY.read_text(encoding="utf-8")
        self.assertNotIn(LEGACY_MARKER, inventory)

    def test_plate_off_blocks_despite_legacy_marker(self):
        plate = {"autonomy": {"enabled": False, "risk_tolerance": "off"}}
        self.assertFalse(
            evaluate_pr(
                plate=plate,
                has_legacy_marker=True,
                plate_file_present=True,
                risk_labels=["risk:low"],
                need_labels=[],
                changed_files=["src/foo.py"],
            )
        )

    def test_plate_present_invalid_blocks_legacy_marker(self):
        self.assertFalse(
            evaluate_pr(
                plate=None,
                has_legacy_marker=True,
                plate_file_present=True,
                risk_labels=["risk:low"],
                need_labels=[],
                changed_files=["src/foo.py"],
            )
        )

    def test_legacy_marker_only_low_tolerance(self):
        self.assertTrue(
            evaluate_pr(
                plate=None,
                has_legacy_marker=True,
                risk_labels=["risk:low"],
                need_labels=[],
                changed_files=["src/foo.py"],
            )
        )
        self.assertFalse(
            evaluate_pr(
                plate=None,
                has_legacy_marker=True,
                risk_labels=["risk:medium"],
                need_labels=[],
                changed_files=["src/foo.py"],
            )
        )

    def test_plate_medium_allows_medium_risk(self):
        plate = {"autonomy": {"enabled": True, "risk_tolerance": "medium"}}
        self.assertTrue(
            evaluate_pr(
                plate=plate,
                has_legacy_marker=False,
                risk_labels=["risk:medium"],
                need_labels=[],
                changed_files=["docs/internal.md"],
            )
        )
        self.assertFalse(
            evaluate_pr(
                plate=plate,
                has_legacy_marker=False,
                risk_labels=["risk:high"],
                need_labels=[],
                changed_files=["docs/internal.md"],
            )
        )

    def test_denylist_paths_block(self):
        plate = {"autonomy": {"enabled": True, "risk_tolerance": "high"}}
        for path in (
            "AGENTS.md",
            "SPEC.md",
            ".github/CODEOWNERS",
            ".github/workflows/ci.yml",
            "README.md",
            ".plate",
        ):
            with self.subTest(path=path):
                self.assertFalse(
                    evaluate_pr(
                        plate=plate,
                        has_legacy_marker=False,
                        risk_labels=["risk:low"],
                        need_labels=[],
                        changed_files=[path],
                    )
                )

    def test_need_human_review_blocks(self):
        plate = {"autonomy": {"enabled": True, "risk_tolerance": "high"}}
        self.assertFalse(
            evaluate_pr(
                plate=plate,
                has_legacy_marker=False,
                risk_labels=["risk:low"],
                need_labels=["need:human-review"],
                changed_files=["src/a.py"],
            )
        )

    def test_workflow_script_contains_precedence_helpers(self):
        script = extract_check_script(read_workflow())
        self.assertIn("function resolveAutonomy", script)
        self.assertIn("hasAutonomySection", script)
        self.assertRegex(script, r"aut\.enabled === true")
        self.assertIn("pathBlocked", script)


class AutoMergeNativeIntegrationUpdate(unittest.TestCase):
    def test_auto_merge_uses_plate_not_marker_only(self):
        """Replaces #1262 item 7: auto-merge reads .plate; marker is legacy fallback only."""
        workflow = read_workflow()
        self.assertIn("path: '.plate'", workflow)
        self.assertIn("resolveAutonomy", workflow)
        self.assertIn(LEGACY_MARKER, workflow)
        self.assertNotIn(
            "active = true",
            workflow.split("getContent")[0],
        )


if __name__ == "__main__":
    unittest.main()