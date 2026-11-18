"""Contract: payload Linux jobs must not hardcode ubuntu-latest (#1489)."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
PAYLOAD_WORKFLOWS = (
    REPO_ROOT / "src" / "plate_core" / "template_payload" / ".github" / "workflows"
)
ALLOWED_HARDCODED = frozenset(
    {
        "windows-latest",
        "windows-2022",
        "macos-latest",
        "macos-14",
        "macos-13",
    }
)
CONFIGURABLE_MARKERS = (
    "vars.CI_RUNS_ON",
    "vars.PLATE_RUNS_ON",
    "fromJSON(needs.",
)


class PayloadWorkflowLinuxRunsOnTests(unittest.TestCase):
    def test_no_linux_job_hardcodes_ubuntu_latest(self):
        violations: list[str] = []
        for path in sorted(PAYLOAD_WORKFLOWS.glob("*.yml")):
            text = path.read_text(encoding="utf-8")
            for doc in yaml.safe_load_all(text):
                if not isinstance(doc, dict):
                    continue
                jobs = doc.get("jobs") or {}
                if not isinstance(jobs, dict):
                    continue
                for job_id, job in jobs.items():
                    if not isinstance(job, dict):
                        continue
                    runs_on = job.get("runs-on")
                    if runs_on is None:
                        continue
                    if isinstance(runs_on, list):
                        continue
                    raw = str(runs_on).strip()
                    if raw in ALLOWED_HARDCODED:
                        continue
                    if raw == "ubuntu-latest":
                        violations.append(f"{path.name} job {job_id}: hardcoded ubuntu-latest")
                        continue
                    if not any(marker in raw for marker in CONFIGURABLE_MARKERS):
                        violations.append(
                            f"{path.name} job {job_id}: unexpected runs-on {raw!r}"
                        )
        self.assertEqual(violations, [])

    def test_build_plate_pr_gates_source_has_no_bare_ubuntu_latest(self):
        script = (
            REPO_ROOT / "scripts" / "build_plate_pr_gates_workflow.py"
        ).read_text(encoding="utf-8")
        for match in re.finditer(r"runs-on:\s*ubuntu-latest", script):
            self.fail(
                "build_plate_pr_gates_workflow.py must use @@LINUX_RUNS_ON@@, "
                f"found bare ubuntu-latest at offset {match.start()}"
            )


if __name__ == "__main__":
    unittest.main()