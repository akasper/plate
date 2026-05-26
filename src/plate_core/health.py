"""Shared health-check logic for gh extension and MCP surfaces."""

from __future__ import annotations

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
    status: str

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
    label_names = {l["name"] for l in labels}
    missing = [x for x in REQUIRED_LABELS if x not in label_names]

    try:
        repo_obj = gh.api(f"repos/{target}")
        default_branch = repo_obj["default_branch"]
        gh.api(f"repos/{target}/branches/{default_branch}/protection")
        protected = True
    except GhApiError:
        protected = False

    search = gh.api(f"search/issues?q=repo:{target}+is:issue+is:open+label:Epic")
    open_epics = int(search.get("total_count", 0))

    label_ok = len(missing) == 0
    if label_ok and protected:
        status = "pass"
    elif label_ok or protected:
        status = "warn"
    else:
        status = "fail"

    return HealthReport(
        repo=target,
        label_coverage_ok=label_ok,
        missing_labels=missing,
        branch_protection_enabled=protected,
        open_epic_count=open_epics,
        status=status,
    )

