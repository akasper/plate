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
    # #634 budget observability (durable spend + .plate autonomy limits)
    budget_enabled: bool | None = None
    budget_risk_tolerance: str | None = None
    budget_remaining_tokens: int | None = None
    budget_daily_limit: int | None = None
    budget_spent_today: int | None = None
    budget_burn_rate: float | None = None
    budget_pressure: str | None = None
    budget_remaining_usd: float | None = None
    budget_would_pause_next_cycle: bool | None = None
    budget_would_throttle_next_cycle: bool | None = None
    # #340 SPEC audit health/drift surface (local, best-effort)
    spec_audit_status: str | None = None  # ok | actionable | advisory | missing | error | skipped
    spec_audit_counts: dict[str, int] = field(default_factory=dict)
    spec_audit_actionable_count: int | None = None
    spec_audit_next_step: str | None = None
    # #953 / #633 adoption readiness (local, best-effort; never fails health alone)
    adoption_core_ready: bool | None = None
    first_qa_seeded: bool | None = None
    adoption_minutes_remaining: int | None = None
    adoption_next_command: str | None = None
    # #967 / #649 self-migrate verify (local, best-effort; never fails health alone)
    self_migrate_drift: bool | None = None
    self_migrate_ready: bool | None = None
    self_migrate_target: str | None = None
    self_migrate_next_command: str | None = None

    def to_dict(self) -> dict:
        d = asdict(self)
        if not d.get("errors"):
            d.pop("errors", None)
        return d


_ACTIONABLE_SPEC_KINDS = frozenset({"undocumented", "stale_evidence", "conflict"})


def summarize_spec_audit_for_health(
    repo_root: str | None = None,
    *,
    enabled: bool = True,
) -> dict:
    """Local SPEC audit summary for health/drift surfaces (#340).

    Never raises; returns status=skipped|missing|error|actionable|advisory|ok.
    Does not auto-edit SPEC.md.
    """
    empty_counts: dict[str, int] = {}
    if not enabled:
        return {
            "spec_audit_status": "skipped",
            "spec_audit_counts": empty_counts,
            "spec_audit_actionable_count": 0,
            "spec_audit_next_step": None,
        }
    try:
        from .spec_audit import audit_spec

        report = audit_spec(repo_root or ".")
    except Exception as exc:
        return {
            "spec_audit_status": "error",
            "spec_audit_counts": empty_counts,
            "spec_audit_actionable_count": 0,
            "spec_audit_next_step": f"SPEC audit failed: {exc}; run gh plate spec-audit for details",
        }

    counts = dict(report.counts or {})
    actionable = sum(int(counts.get(k, 0) or 0) for k in _ACTIONABLE_SPEC_KINDS)

    if report.error or not report.ok:
        err = str(report.error or "audit failed")
        status = "missing" if "not found" in err.lower() else "error"
        step = (
            "Create or restore SPEC.md then re-run gh plate health / gh plate spec-audit"
            if status == "missing"
            else f"SPEC audit error: {err}; run gh plate spec-audit"
        )
        return {
            "spec_audit_status": status,
            "spec_audit_counts": counts,
            "spec_audit_actionable_count": actionable,
            "spec_audit_next_step": step,
        }

    if actionable > 0:
        return {
            "spec_audit_status": "actionable",
            "spec_audit_counts": counts,
            "spec_audit_actionable_count": actionable,
            "spec_audit_next_step": (
                f"Resolve {actionable} SPEC audit finding(s) "
                f"(undocumented={counts.get('undocumented', 0)}, "
                f"stale_evidence={counts.get('stale_evidence', 0)}, "
                f"conflict={counts.get('conflict', 0)}): "
                "gh plate spec-audit --json then --followups / Documentation PR "
                "(never auto-write SPEC.md without human approval)"
            ),
        }

    if int(counts.get("future_ok", 0) or 0) > 0 and int(counts.get("aligned", 0) or 0) == 0:
        return {
            "spec_audit_status": "advisory",
            "spec_audit_counts": counts,
            "spec_audit_actionable_count": 0,
            "spec_audit_next_step": (
                "SPEC has future_ok sections without aligned fragment evidence; "
                "review with gh plate spec-audit (not an error)"
            ),
        }

    return {
        "spec_audit_status": "ok",
        "spec_audit_counts": counts,
        "spec_audit_actionable_count": 0,
        "spec_audit_next_step": None,
    }


def _repo_from_git_remote() -> str:
    proc = subprocess.run(
        ["git", "config", "--get", "remote.origin.url"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            "Could not determine repo from git remote origin.\n"
            "Run from inside the target project's checkout, or pass --repo owner/name."
        )
    remote = proc.stdout.strip()
    # Supports both git@github.com:owner/repo.git and https://github.com/owner/repo(.git)
    # Note: repo name may contain dots (e.g. "u.ai"), so capture allows [^/]+ (non-greedy before optional .git)
    # .git ambiguity note (per review of #609/#608): the optional (?:\.git)?$ trailer means repo names
    # legitimately ending in ".git" (e.g. "myrepo.git" remote) will have the suffix stripped from capture
    # (treated as remote trailer). "foo.git.git" parses as "foo.git" (non-greedy prefers trailer match).
    # This is a known limitation for the rare case of .git-suffixed repo names; common dotted names
    # (u.ai etc) now work. Parametrized regression test added.
    m = re.search(r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?$", remote)
    if not m:
        raise RuntimeError(
            f"Remote origin is not a GitHub repository URL: {remote!r}\n"
            "Run from inside the target project's checkout (with a github.com origin remote), "
            "or pass --repo owner/name explicitly."
        )
    return f"{m.group('owner')}/{m.group('repo')}"


def resolve_repo(repo: str | None) -> str:
    return repo if repo else _repo_from_git_remote()


def get_health(
    repo: str | None = None,
    client: GhClient | None = None,
    *,
    repo_root: str | None = None,
    include_spec_audit: bool = True,
) -> HealthReport:
    gh = client or GhClient()
    # resolve_repo (and _repo_from_git_remote) raise RuntimeError with clear messages on failure;
    # the previous try/except wrapper added no value (unnecessary per review of #609).
    # Propagate directly so original error (with its guidance about --repo) is surfaced.
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

    # #634: best-effort durable budget snapshot for health CLI/MCP (no hard fail)
    budget_enabled: bool | None = None
    budget_risk_tolerance: str | None = None
    budget_remaining_tokens: int | None = None
    budget_daily_limit: int | None = None
    budget_spent_today: int | None = None
    budget_burn_rate: float | None = None
    budget_pressure: str | None = None
    budget_remaining_usd: float | None = None
    budget_would_pause_next_cycle: bool | None = None
    budget_would_throttle_next_cycle: bool | None = None
    try:
        from .autonomy import get_budget_snapshot

        snap = get_budget_snapshot()
        if isinstance(snap, dict):
            budget_enabled = bool(snap.get("enabled")) if "enabled" in snap else None
            budget_risk_tolerance = (
                str(snap.get("risk_tolerance")) if snap.get("risk_tolerance") is not None else None
            )
            if snap.get("remaining_tokens") is not None:
                budget_remaining_tokens = int(snap.get("remaining_tokens") or 0)
            if snap.get("daily_limit") is not None:
                budget_daily_limit = int(snap.get("daily_limit") or 0)
            if snap.get("spent_today") is not None:
                budget_spent_today = int(snap.get("spent_today") or 0)
            if snap.get("burn_rate") is not None:
                budget_burn_rate = float(snap.get("burn_rate") or 0.0)
            if snap.get("budget_pressure") is not None:
                budget_pressure = str(snap.get("budget_pressure"))
            if snap.get("remaining_usd") is not None:
                budget_remaining_usd = float(snap.get("remaining_usd"))
            if snap.get("would_pause_next_cycle") is not None:
                budget_would_pause_next_cycle = bool(snap.get("would_pause_next_cycle"))
            elif snap.get("would_pause") is not None:
                budget_would_pause_next_cycle = bool(snap.get("would_pause"))
            if snap.get("would_throttle_next_cycle") is not None:
                budget_would_throttle_next_cycle = bool(
                    snap.get("would_throttle_next_cycle")
                )
            elif snap.get("would_throttle") is not None:
                budget_would_throttle_next_cycle = bool(snap.get("would_throttle"))
    except Exception as e:
        errors.append(f"budget: {e}")

    # #340: local SPEC audit drift signal (best-effort; does not fail health alone)
    spec_audit_status: str | None = None
    spec_audit_counts: dict[str, int] = {}
    spec_audit_actionable_count: int | None = None
    spec_audit_next_step: str | None = None
    try:
        sa = summarize_spec_audit_for_health(
            repo_root if repo_root is not None else ".",
            enabled=include_spec_audit,
        )
        spec_audit_status = sa.get("spec_audit_status")
        spec_audit_counts = dict(sa.get("spec_audit_counts") or {})
        if sa.get("spec_audit_actionable_count") is not None:
            spec_audit_actionable_count = int(sa.get("spec_audit_actionable_count") or 0)
        spec_audit_next_step = sa.get("spec_audit_next_step")
    except Exception as e:
        errors.append(f"spec_audit: {e}")
        spec_audit_status = "error"
        spec_audit_next_step = f"SPEC audit health summary failed: {e}"

    # #953 / #633: local adoption readiness (best-effort; does not fail health alone)
    adoption_core_ready: bool | None = None
    first_qa_seeded: bool | None = None
    adoption_minutes_remaining: int | None = None
    adoption_next_command: str | None = None
    try:
        from .adoption import assess_adoption_readiness

        adopt = assess_adoption_readiness(
            repo_root if repo_root is not None else ".",
            include_optional=False,
        )
        if adopt.get("ok"):
            adoption_core_ready = bool(adopt.get("core_ready"))
            fq = adopt.get("first_qa") or {}
            if isinstance(fq, dict) and "seeded" in fq:
                first_qa_seeded = bool(fq.get("seeded"))
            if adopt.get("estimated_minutes_remaining") is not None:
                adoption_minutes_remaining = int(adopt.get("estimated_minutes_remaining") or 0)
            if adopt.get("next_command"):
                adoption_next_command = str(adopt.get("next_command"))
    except Exception as e:
        errors.append(f"adoption: {e}")

    # #967 / #649: local self-migrate verify (best-effort; does not fail health alone)
    self_migrate_drift: bool | None = None
    self_migrate_ready: bool | None = None
    self_migrate_target: str | None = None
    self_migrate_next_command: str | None = None
    try:
        from .self_migrate import verify_self_migrate

        sm = verify_self_migrate(repo_root if repo_root is not None else ".")
        if sm.get("ok"):
            migrate = sm.get("migrate") or {}
            if "drift" in migrate:
                self_migrate_drift = bool(migrate.get("drift"))
            elif "drift" in sm:
                self_migrate_drift = bool(sm.get("drift"))
            if "ready" in sm:
                self_migrate_ready = bool(sm.get("ready"))
            # Do not shadow outer `target` (GitHub owner/name used for report.repo).
            sm_target = migrate.get("target_version") or sm.get("target_version")
            if sm_target:
                self_migrate_target = str(sm_target)
            if sm.get("next_command"):
                self_migrate_next_command = str(sm.get("next_command"))
    except Exception as e:
        errors.append(f"self_migrate: {e}")

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
        budget_enabled=budget_enabled,
        budget_risk_tolerance=budget_risk_tolerance,
        budget_remaining_tokens=budget_remaining_tokens,
        budget_daily_limit=budget_daily_limit,
        budget_spent_today=budget_spent_today,
        budget_burn_rate=budget_burn_rate,
        budget_pressure=budget_pressure,
        budget_remaining_usd=budget_remaining_usd,
        budget_would_pause_next_cycle=budget_would_pause_next_cycle,
        budget_would_throttle_next_cycle=budget_would_throttle_next_cycle,
        spec_audit_status=spec_audit_status,
        spec_audit_counts=spec_audit_counts,
        spec_audit_actionable_count=spec_audit_actionable_count,
        spec_audit_next_step=spec_audit_next_step,
        adoption_core_ready=adoption_core_ready,
        first_qa_seeded=first_qa_seeded,
        adoption_minutes_remaining=adoption_minutes_remaining,
        adoption_next_command=adoption_next_command,
        self_migrate_drift=self_migrate_drift,
        self_migrate_ready=self_migrate_ready,
        self_migrate_target=self_migrate_target,
        self_migrate_next_command=self_migrate_next_command,
    )
    return report
