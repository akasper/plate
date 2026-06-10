"""Shared health-check logic for gh extension and MCP surfaces."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import asdict, dataclass, field

from .github_client import GhApiError, GhClient


REQUIRED_LABELS = ["Bug", "Feature", "Epic", "Documentation", "Research", "Design", "Question", "Task"]


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
    errors: list[str] = field(default_factory=list)  # partial failure details for resilience (#270)
    open_question_count: int = 0
    plate_config_present: bool = False
    plate_config_valid: bool = False
    plate_config_file_version: str | None = None
    plate_config_resolved_version: str | None = None
    plate_config_upgrade_available: bool = False
    plate_config_enabled_extensions: list[str] = field(default_factory=list)
    curiosity_answers_present: bool = False
    plate_repo_signals: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        if not d.get("errors"):
            d.pop("errors", None)
        return d


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
    errors: list[str] = []

    try:
        labels = gh.api(f"repos/{target}/labels?per_page=100")
        label_names = {l["name"].lower() for l in labels}
        missing = [x for x in REQUIRED_LABELS if x.lower() not in label_names]
    except GhApiError as e:
        errors.append(f"labels: {e}")
        label_names = set()
        missing = list(REQUIRED_LABELS)  # assume all missing on failure

    try:
        repo_obj = gh.api(f"repos/{target}")
        default_branch = repo_obj["default_branch"]
        gh.api(f"repos/{target}/branches/{default_branch}/protection")
        protected = True
    except GhApiError as e:
        protected = False
        errors.append(f"branch_protection: {e}")

    try:
        search = gh.api(f"search/issues?q=repo:{target}+is:issue+is:open+label:Epic")
        open_epics = int(search.get("total_count", 0))
    except GhApiError as e:
        open_epics = 0
        errors.append(f"open_epics: {e}")

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
    plate_config_file_version = None
    plate_config_resolved_version = None
    plate_config_upgrade_available = False
    plate_config_enabled_extensions: list[str] = []
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
                from .plate_config import upgrade_plate_config_dict, validate_plate_config
                validate_plate_config(data)
                upgraded, _guidance, previous_version = upgrade_plate_config_dict(data)
                plate_config_valid = True
                plate_config_file_version = previous_version
                plate_config_resolved_version = upgraded["version"]
                plate_config_upgrade_available = previous_version != upgraded["version"]
                extensions = upgraded.get("extensions", {})
                installed = extensions.get("installed", {})
                if extensions.get("enabled", True) and isinstance(installed, dict):
                    for extension_id, settings in installed.items():
                        if settings is True:
                            plate_config_enabled_extensions.append(extension_id)
                        elif isinstance(settings, dict) and settings.get("enabled", True):
                            plate_config_enabled_extensions.append(extension_id)
            except Exception:
                plate_config_valid = False
    except GhApiError:
        plate_config_present = False
        plate_config_valid = False

    # Curiosity adoption signal (for #262: Curiosity adoption signals, answers index)
    curiosity_answers_present = False
    try:
        gh.api(f"repos/{target}/contents/docs/curiosity/answers.yml")
        curiosity_answers_present = True
    except GhApiError:
        try:
            gh.api(f"repos/{target}/contents/docs/curiosity/answers.json")
            curiosity_answers_present = True
        except GhApiError:
            curiosity_answers_present = False

    # PLATE repo detection signals (for #459 / #464 default persona activation)
    # Strong local signal: .plate/config (already computed); supplement with other common signals.
    plate_repo_signals: list[str] = []
    if plate_config_present:
        plate_repo_signals.append(".plate/config present")
    try:
        gh.api(f"repos/{target}/contents/AGENTS.md")
        plate_repo_signals.append("AGENTS.md present")
    except GhApiError:
        pass
    try:
        gh.api(f"repos/{target}/contents/.agentic")
        plate_repo_signals.append(".agentic/ present")
    except GhApiError:
        pass
    if open_epics > 0:
        plate_repo_signals.append("open Epic issues (GitHub signal)")

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
    except Exception as e:
        binary_artifacts_tracked = -1  # unknown in this environment
        errors.append(f"binary_artifacts: {e}")

    # Goals page convention discovery / nudge (Epic #218 / #229): agents + health surfaces can reliably detect adoption of docs/wiki/Goals.md
    goals_page_present = False
    try:
        gh.api(f"repos/{target}/contents/docs/wiki/Goals.md")
        goals_page_present = True
    except GhApiError:
        pass
    except Exception:
        pass  # defensive; presence is best-effort

    label_ok = len(missing) == 0
    hygiene_ok = binary_artifacts_tracked == 0
    if label_ok and protected and hygiene_ok:
        status = "pass"
    elif label_ok or protected or hygiene_ok:
        status = "warn"
    else:
        status = "fail"

    report = HealthReport(
        repo=target,
        label_coverage_ok=label_ok,
        missing_labels=missing,
        branch_protection_enabled=protected,
        open_epic_count=open_epics,
        binary_artifacts_tracked=binary_artifacts_tracked,
        goals_page_present=goals_page_present,
        status=status,
        errors=errors,
        open_question_count=open_question_count,
        plate_config_present=plate_config_present,
        plate_config_valid=plate_config_valid,
        plate_config_file_version=plate_config_file_version,
        plate_config_resolved_version=plate_config_resolved_version,
        plate_config_upgrade_available=plate_config_upgrade_available,
        plate_config_enabled_extensions=plate_config_enabled_extensions,
        curiosity_answers_present=curiosity_answers_present,
        plate_repo_signals=plate_repo_signals,
    )
    return report
