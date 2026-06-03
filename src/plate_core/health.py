"""Shared health-check logic for gh extension and MCP surfaces."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import asdict, dataclass

from .github_client import GhApiError, GhClient


REQUIRED_LABELS = ["Bug", "Feature", "Epic", "Documentation", "Research", "Design", "Question"]


@dataclass
class HealthReport:
    repo: str
    label_coverage_ok: bool
    missing_labels: list[str]
    branch_protection_enabled: bool
    open_epic_count: int
    binary_artifacts_tracked: int
    status: str
    goals_page_present: bool = False
    open_question_count: int = 0
    plate_config_present: bool = False
    plate_config_valid: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def _repo_from_git_remote() -> str:
    proc = subprocess.run(
        ["git", "config", "--get", "remote.origin.url"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError("Could not determine repo from git remote; pass --repo owner/name.")
    remote = proc.stdout.strip()
    # Supports both git@github.com:owner/repo.git and https://github.com/owner/repo(.git)
    m = re.search(r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/.]+)(?:\.git)?$", remote)
    if not m:
        raise RuntimeError("Remote origin is not a GitHub repository URL.")
    return f"{m.group('owner')}/{m.group('repo')}"


def resolve_repo(repo: str | None) -> str:
    return repo if repo else _repo_from_git_remote()


def get_health(repo: str | None = None, client: GhClient | None = None) -> HealthReport:
    gh = client or GhClient()
    target = resolve_repo(repo)

    labels = gh.api(f"repos/{target}/labels?per_page=100")
    label_names = {l["name"].lower() for l in labels}
    missing = [x for x in REQUIRED_LABELS if x.lower() not in label_names]

    try:
        repo_obj = gh.api(f"repos/{target}")
        default_branch = repo_obj["default_branch"]
        gh.api(f"repos/{target}/branches/{default_branch}/protection")
        protected = True
    except GhApiError:
        protected = False

    search = gh.api(f"search/issues?q=repo:{target}+is:issue+is:open+label:Epic")
    open_epics = int(search.get("total_count", 0))

    # Goals page (from #229 bootstrap / #262 health expansion)
    goals_page_present = False
    try:
        gh.api(f"repos/{target}/contents/docs/wiki/Goals.md")
        goals_page_present = True
    except GhApiError:
        goals_page_present = False

    # Open Questions count (for #262, curiosity health)
    try:
        qsearch = gh.api(f"search/issues?q=repo:{target}+is:issue+is:open+label:Question")
        open_question_count = int(qsearch.get("total_count", 0))
    except Exception:
        open_question_count = 0

    # .plate/config validity (for #262 health expansion, #259)
    plate_config_present = False
    plate_config_valid = False
    try:
        plate_content = gh.api(f"repos/{target}/contents/.plate")
        if isinstance(plate_content, dict) and plate_content.get("type") == "file":
            plate_config_present = True
            try:
                import base64
                content = plate_content.get("content", "")
                if plate_content.get("encoding") == "base64":
                    content = base64.b64decode(content).decode("utf-8")
                data = json.loads(content)
                from .plate_config import validate_plate_config, PlateConfigError
                validate_plate_config(data)
                plate_config_valid = True
            except Exception:
                plate_config_valid = False
    except GhApiError:
        plate_config_present = False
        plate_config_valid = False

    # Binary artifact hygiene check (addresses Bug #90 / #91 regression guard)
    # Uses git ls-files to detect any tracked .pyc, __pycache__, or common binaries
    binary_artifacts_tracked = 0
    try:
        proc = subprocess.run(
            ["git", "ls-files", "--cached"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        if proc.returncode == 0:
            tracked_files = proc.stdout.splitlines()
            forbidden_suffixes = (".pyc", ".pyo", ".pyd", ".so", ".dll", ".dylib")
            binary_artifacts_tracked = sum(
                1
                for f in tracked_files
                if f.endswith(forbidden_suffixes) or "__pycache__" in f or "/__pycache__/" in f
            )
    except Exception:
        binary_artifacts_tracked = -1  # unknown in this environment

    label_ok = len(missing) == 0
    hygiene_ok = binary_artifacts_tracked == 0
    if label_ok and protected and hygiene_ok:
        status = "pass"
    elif label_ok or protected or hygiene_ok:
        status = "warn"
    else:
        status = "fail"

    return HealthReport(
        repo=target,
        label_coverage_ok=label_ok,
        missing_labels=missing,
        branch_protection_enabled=protected,
        open_epic_count=open_epics,
        binary_artifacts_tracked=binary_artifacts_tracked,
        status=status,
        goals_page_present=goals_page_present,
        open_question_count=open_question_count,
        plate_config_present=plate_config_present,
        plate_config_valid=plate_config_valid,
    )

