"""Pure lifecycle policy: approvers, gate defaults, and shadow decisions (#1425).

This module is intentionally **side-effect free**: it does not call GitHub, mutate
labels, or enqueue auto-merge. Integration with wake loops, event logs (#1443),
and leases (#1445) stays behind explicit call sites.

Contract references: #1425 (slice 4), design #1420, related #1374 / #1398.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import yaml

PROCESS_REL = ".agentic/process.yml"

# Ordered low → high; used with stricter-wins helpers.
RISK_TOLERANCE_RANK: dict[str, int] = {
    "off": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
}

# Balanced defaults (#1425): True = gate is "open" for policy checks that consult this map.
DEFAULT_LIFECYCLE_GATES: dict[str, bool] = {
    "merge": True,
    "start_tier_T3": True,
    "risk_critical": True,
    "release_cut": True,
    "deploy_publish": True,
    "protected_paths": True,
    "epic_open_close": True,
    "abandon_human_filed": True,
    "non_collaborator_ready": True,
    "start": False,
    "file_issue": False,
    "issue_over_allocation": False,
    # Fixed / human-only in full lifecycle; kept False so defaults never waive human review.
    "gate_label_downgrade": False,
    "project_budget": False,
    "license": False,
}

# Substrings that identify PLATE marker comments / pending write hints (#1425).
_PENDING_WRITE_MARKERS: tuple[str, ...] = (
    "PLATE_PENDING_WRITE",
    "pending_write",
    "<!-- PLATE",
)

_APPROVAL_COMMAND_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^\s*/plate\s+resume\b", re.I),
    re.compile(r"^\s*/plate\s+approve\b", re.I),
)


def risk_tolerance_rank(value: str | None) -> int:
    """Return numeric rank for ``autonomy.risk_tolerance`` (unknown → 0, fail closed)."""
    if not value:
        return 0
    return RISK_TOLERANCE_RANK.get(str(value).strip().lower(), 0)


def parse_first_line(comment_body: str | None) -> str:
    """First line only (#1425 approval commands); ignores the rest of the comment."""
    if not comment_body:
        return ""
    text = str(comment_body).replace("\r\n", "\n").replace("\r", "\n")
    return text.split("\n", 1)[0].strip()


def comment_has_pending_write_suppression(body: str | None) -> bool:
    """True when comment body suggests an in-flight PLATE pending write (best-effort)."""
    if not body:
        return False
    lower = body.lower()
    return any(m.lower() in lower for m in _PENDING_WRITE_MARKERS)


def parse_plate_approval_command(first_line: str) -> str | None:
    """If the first line starts a /plate resume|approve command, return its kind."""
    line = (first_line or "").strip()
    if not line:
        return None
    for pat in _APPROVAL_COMMAND_PATTERNS:
        m = pat.match(line)
        if m:
            if "resume" in m.group(0).lower():
                return "resume"
            return "approve"
    return None


def _normalize_label(label: str) -> str:
    return str(label or "").strip()


def label_indicates_downgrade(
    prev_labels: Sequence[str],
    new_labels: Sequence[str],
) -> tuple[bool, list[str]]:
    """Detect removals that qualify as approver-only downgrades (#1425).

    Downgrade = removing any of ``risk:*``, ``tier:*``, ``need:human-review``,
    ``need:security-review`` from the issue label set.
    """
    prev = {_normalize_label(x) for x in prev_labels if _normalize_label(x)}
    new = {_normalize_label(x) for x in new_labels if _normalize_label(x)}
    removed = prev - new
    downgrade_labels = [
        x
        for x in removed
        if x.startswith("risk:")
        or x.startswith("tier:")
        or x in ("need:human-review", "need:security-review")
    ]
    return bool(downgrade_labels), downgrade_labels


def label_indicates_critical_raise(
    prev_labels: Sequence[str],
    new_labels: Sequence[str],
) -> tuple[bool, bool]:
    """Return (raised, already_critical) for transition to ``risk:critical``."""
    prev = {_normalize_label(x).lower() for x in prev_labels}
    new = {_normalize_label(x).lower() for x in new_labels}
    critical = "risk:critical"
    already = critical in prev
    raised = critical in new and not already
    return raised, already


def _coerce_bool_map(data: Any, ctx: str) -> dict[str, bool]:
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(f"{ctx} must be a mapping")
    out: dict[str, bool] = {}
    for k, v in data.items():
        if not isinstance(k, str) or not k.strip():
            raise ValueError(f"{ctx} keys must be non-empty strings")
        out[k.strip()] = bool(v)
    return out


def merged_lifecycle_gates(yaml_fragment: Mapping[str, Any] | None) -> dict[str, bool]:
    """DEFAULT_LIFECYCLE_GATES overwritten by ``lifecycle.gates`` from YAML."""
    base = dict(DEFAULT_LIFECYCLE_GATES)
    if not yaml_fragment:
        return base
    life = yaml_fragment.get("lifecycle")
    if not isinstance(life, dict):
        return base
    gates = life.get("gates")
    if gates is None:
        return base
    overrides = _coerce_bool_map(gates, "lifecycle.gates")
    base.update(overrides)
    return base


def gate_requires_human_review(key: str, gates: Mapping[str, bool] | None = None) -> bool:
    """True when this gate key is closed or fixed human-only (immutable human gates)."""
    g = dict(gates) if gates is not None else merged_lifecycle_gates(None)
    if key in ("gate_label_downgrade", "project_budget", "license"):
        return True
    return not bool(g.get(key, False))


def stricter_autonomy_cap(
    *,
    gate_allows: bool,
    risk_tolerance: str | None,
    action_needs_min_tolerance: str = "medium",
) -> tuple[bool, str]:
    """Apply gate first, then cap by ``autonomy.risk_tolerance`` (stricter wins)."""
    if not gate_allows:
        return False, "lifecycle gate closed"
    need = risk_tolerance_rank(action_needs_min_tolerance)
    have = risk_tolerance_rank(risk_tolerance)
    if have < need:
        return False, f"risk_tolerance caps action (have {have}, need {need})"
    return True, "ok"


def match_labels_by_taxonomy(
    labels: Iterable[str],
    *,
    risk: str | None = None,
    tier: str | None = None,
    issue_type: str | None = None,
) -> bool:
    """Match issue labels using attribute prefixes, not free-form taxonomy strings."""
    norm = {_normalize_label(x) for x in labels if _normalize_label(x)}
    if risk is not None:
        if f"risk:{risk}" not in norm:
            return False
    if tier is not None:
        if f"tier:{tier}" not in norm:
            return False
    if issue_type is not None:
        if issue_type not in norm:
            return False
    return True


@dataclass
class ResolvedApprovers:
    """Outcome of resolving who may approve lifecycle actions for a repository."""

    logins: tuple[str, ...]
    source: str  # explicit_config | owner_fallback | none
    refuse_all: bool
    reason: str = ""


def _owner_login_from_repo(repo_obj: Mapping[str, Any] | None) -> str | None:
    if not repo_obj:
        return None
    owner = repo_obj.get("owner")
    if isinstance(owner, dict):
        login = owner.get("login")
        if isinstance(login, str) and login.strip():
            return login.strip()
    return None


def _read_lifecycle_block(repo_root: Path) -> dict[str, Any]:
    path = repo_root / PROCESS_REL
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {}
    life = data.get("lifecycle")
    return life if isinstance(life, dict) else {}


def read_lifecycle_block(repo_root: Path) -> dict[str, Any]:
    """Return the ``lifecycle`` mapping from ``.agentic/process.yml`` (empty if missing)."""
    return _read_lifecycle_block(repo_root)


def fetch_token_user_login(gh: Any) -> str:
    """Return ``login`` from ``GET /user`` (raises ValueError on failure)."""
    data = gh.api("user")
    if not isinstance(data, dict):
        raise ValueError("unexpected /user response")
    login = data.get("login")
    if not isinstance(login, str) or not login.strip():
        raise ValueError("missing login in /user response")
    return login.strip()


def fetch_repo(owner_name: str, gh: Any) -> dict[str, Any]:
    """Return repository object for ``owner/name``."""
    data = gh.api(f"repos/{owner_name}")
    if not isinstance(data, dict):
        raise ValueError(f"unexpected repos/{owner_name} response")
    return data


def parse_lifecycle_approvers_list(raw: Any) -> tuple[str, ...] | None:
    """Return normalized logins or None if key absent, () if empty list."""
    if raw is None:
        return None
    if not isinstance(raw, list):
        raise ValueError("lifecycle.approvers must be a list of strings when present")
    out: list[str] = []
    for item in raw:
        if not isinstance(item, str) or not item.strip():
            raise ValueError("lifecycle.approvers entries must be non-empty strings")
        out.append(item.strip().lower())
    return tuple(out)


def resolve_runtime_approvers(
    *,
    lifecycle_yaml: Mapping[str, Any] | None,
    token_user_login: str | None,
    repo_obj: Mapping[str, Any] | None,
) -> ResolvedApprovers:
    """Resolve effective approver set (fail closed when unset or empty)."""
    life = lifecycle_yaml or {}
    raw = life.get("approvers")
    org = bool(repo_obj.get("owner", {}).get("type") == "Organization") if isinstance(
        repo_obj, dict
    ) else False

    if raw is None:
        if org:
            return ResolvedApprovers((), "none", True, "org repo requires explicit lifecycle.approvers")
        owner = _owner_login_from_repo(repo_obj)
        if not owner:
            return ResolvedApprovers((), "none", True, "cannot resolve repo owner for approver fallback")
        return ResolvedApprovers((owner.lower(),), "owner_fallback", False, "")

    try:
        approvers = parse_lifecycle_approvers_list(raw)
    except ValueError as exc:
        return ResolvedApprovers((), "none", True, str(exc))

    assert approvers is not None
    if len(approvers) == 0:
        return ResolvedApprovers((), "explicit_config", True, "empty lifecycle.approvers")

    return ResolvedApprovers(approvers, "explicit_config", False, "")


def is_approver(
    actor_login: str | None,
    resolved: ResolvedApprovers,
) -> bool:
    if resolved.refuse_all or not actor_login:
        return False
    return actor_login.strip().lower() in resolved.logins


def plan_init_process_yaml(
    *,
    token_user_login: str,
    repo_obj: Mapping[str, Any] | None,
    org_approvers: Sequence[str] | None,
    explicit_user_approvers: Sequence[str] | None = None,
    confirm_non_owner: bool = False,
) -> dict[str, Any]:
    """Build ``lifecycle`` block for ``.agentic/process.yml`` at init/bootstrap time.

    - User-owned repo: approvers default to the token user **only** when that user is
      the repository owner (``owner.login``); otherwise require ``confirm_non_owner``.
      Optional ``explicit_user_approvers`` overrides the default list (e.g. multiple humans).
    - Organization: **must** pass explicit ``org_approvers`` (non-empty).
    """
    tu = token_user_login.strip().lower()
    if not tu:
        raise ValueError("token_user_login is required")

    gates_payload = {"approvers": None, "gates": copy.deepcopy(DEFAULT_LIFECYCLE_GATES)}

    org = bool(repo_obj and repo_obj.get("owner", {}).get("type") == "Organization")
    if org:
        if not org_approvers:
            raise ValueError("organization repository requires explicit approvers")
        apps = [a.strip().lower() for a in org_approvers if isinstance(a, str) and a.strip()]
        if not apps:
            raise ValueError("organization approvers list is empty")
        gates_payload["approvers"] = apps
        return {"lifecycle": gates_payload}

    owner = _owner_login_from_repo(repo_obj)
    if owner is None:
        raise ValueError("cannot read owner.login from repo object")
    owner_l = owner.lower()
    if explicit_user_approvers:
        apps = [a.strip().lower() for a in explicit_user_approvers if isinstance(a, str) and a.strip()]
        if not apps:
            raise ValueError("explicit user approvers list is empty")
        gates_payload["approvers"] = apps
        return {"lifecycle": gates_payload}

    if tu != owner_l and not confirm_non_owner:
        raise ValueError(
            "token user does not match repo owner.login; re-run with confirm_non_owner"
        )
    gates_payload["approvers"] = [tu]
    return {"lifecycle": gates_payload}


def apply_lifecycle_fragment(existing: dict[str, Any], fragment: dict[str, Any]) -> dict[str, Any]:
    """Deep-merge mappings from *fragment* into a copy of *existing* (YAML root).

    Dict values merge recursively; lists and scalars replace. Missing keys on the
    left are added from the right.
    """

    def _merge(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
        result = copy.deepcopy(a)
        for key, val in b.items():
            if key in result and isinstance(result[key], dict) and isinstance(val, dict):
                result[key] = _merge(result[key], val)
            else:
                result[key] = copy.deepcopy(val)
        return result

    return _merge(existing, fragment)


def write_process_yaml_lifecycle(
    repo_root: Path,
    fragment: dict[str, Any],
    *,
    create: bool = True,
) -> Path:
    """Merge *fragment* into ``.agentic/process.yml`` and write. Used by ``gh plate process init``."""
    path = repo_root / PROCESS_REL
    if path.is_file():
        current = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(current, dict):
            current = {}
    else:
        if not create:
            raise FileNotFoundError(str(path))
        path.parent.mkdir(parents=True, exist_ok=True)
        current = {}
    merged = apply_lifecycle_fragment(current, fragment)
    path.write_text(yaml.safe_dump(merged, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path


# --- Rolling-hour critical raise (pure) ---


@dataclass
class CriticalRaiseEvent:
    actor: str
    when: datetime


@dataclass
class RollingCriticalRaiseTracker:
    """In-memory tracker for non-approver ``risk:critical`` raises in a rolling hour."""

    window: timedelta = field(default_factory=lambda: timedelta(hours=1))
    events: list[CriticalRaiseEvent] = field(default_factory=list)

    def prune(self, *, now: datetime | None = None) -> None:
        n = now or datetime.now(timezone.utc)
        cutoff = n - self.window
        self.events = [e for e in self.events if e.when >= cutoff]

    def record(self, actor: str, *, now: datetime | None = None) -> None:
        n = now or datetime.now(timezone.utc)
        self.prune(now=n)
        self.events.append(CriticalRaiseEvent(actor=actor.strip().lower(), when=n))

    def count_for_actor(self, actor: str) -> int:
        a = actor.strip().lower()
        return sum(1 for e in self.events if e.actor == a)


@dataclass(frozen=True)
class ShadowLabelChangeDecision:
    """Pure outcome for a proposed issue label mutation."""

    allowed: bool
    kind: str
    reasons: tuple[str, ...] = ()


def decide_issue_label_change(
    *,
    prev_labels: Sequence[str],
    new_labels: Sequence[str],
    actor_login: str | None,
    resolved: ResolvedApprovers,
    critical_tracker: RollingCriticalRaiseTracker | None,
    now: datetime | None = None,
) -> ShadowLabelChangeDecision:
    """Fail-closed policy for shadow simulation (#1425; no GitHub writes)."""
    actor = (actor_login or "").strip().lower()

    downgrade, removed = label_indicates_downgrade(prev_labels, new_labels)
    if downgrade:
        if is_approver(actor, resolved):
            return ShadowLabelChangeDecision(True, "downgrade_ok_approver", ())
        return ShadowLabelChangeDecision(
            False,
            "downgrade_reverted",
            (f"removing labels requires approver: {', '.join(removed)}",),
        )

    raised, _already = label_indicates_critical_raise(prev_labels, new_labels)
    if raised:
        if is_approver(actor, resolved):
            return ShadowLabelChangeDecision(True, "critical_raise_approver", ())
        if critical_tracker is None:
            critical_tracker = RollingCriticalRaiseTracker()
        critical_tracker.record(actor, now=now)
        if critical_tracker.count_for_actor(actor) >= 4:
            return ShadowLabelChangeDecision(
                False,
                "critical_raise_rate_limited",
                ("fourth risk:critical raise in rolling hour by non-approver",),
            )
        return ShadowLabelChangeDecision(True, "critical_raise_ok", ())

    return ShadowLabelChangeDecision(True, "no_policy_trigger", ())


@dataclass(frozen=True)
class ShadowApprovalCommandDecision:
    allowed: bool
    kind: str
    reasons: tuple[str, ...] = ()


def decide_approval_command(
    *,
    comment_body: str | None,
    actor_login: str | None,
    resolved: ResolvedApprovers,
) -> ShadowApprovalCommandDecision:
    """First-line-only /plate resume|approve; approver-only; pending_write blocks."""
    first = parse_first_line(comment_body)
    cmd = parse_plate_approval_command(first)
    if cmd is None:
        return ShadowApprovalCommandDecision(False, "not_approval_command", ())

    if comment_has_pending_write_suppression(comment_body):
        return ShadowApprovalCommandDecision(False, "pending_write", ("pending_write present",))

    if not is_approver(actor_login, resolved):
        return ShadowApprovalCommandDecision(False, "approver_required", ("actor is not an approver",))

    return ShadowApprovalCommandDecision(True, f"approval_cmd_{cmd}", ())


def assert_no_path_removes_human_review(module_names: Sequence[str]) -> None:
    """Guardrail: PLATE modules must not reference removing ``need:human-review``."""
    import importlib
    import inspect

    forbidden = re.compile(
        r"\bremove\b.*need:human-review|need:human-review.*\bremove\b",
        re.I,
    )
    for name in module_names:
        mod = importlib.import_module(name)
        src = inspect.getsource(mod)
        if forbidden.search(src):
            raise AssertionError(f"forbidden human-review removal reference in {name}")


def pl_allowed_code_paths_for_human_review_audit() -> tuple[str, ...]:
    """Modules scanned by ``test_no_code_path_removes_human_review``."""
    return ("plate_core.lifecycle_policy",)
