"""Pure lifecycle policy: approvers, gate keys, and shadow decisions (#1425).

This module is intentionally **side-effect free**: it does not call GitHub, mutate
labels, or enqueue auto-merge. Integration with wake loops, event logs (#1443),
and leases (#1445) stays behind explicit call sites.

Contract references: #1425 (slice 4), design #1420, related #1374 / #1398.

**Gate semantics (canonical):** Matches design PR
https://github.com/akasper/plate/pull/1432 — in ``lifecycle.gates``, ``true`` means
**human approval is required** for that gate; ``false`` means this gate does not add
that requirement in the bounded policy layer.
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

_SENTINEL = object()

# Ordered low → high; used with stricter-wins helpers.
RISK_TOLERANCE_RANK: dict[str, int] = {
    "off": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
}

# Ordered least → most severe (for ``risk:*`` label bodies after the prefix).
RISK_SEVERITY_ORDER: tuple[str, ...] = ("low", "medium", "high", "critical")

# Canonical PLATE tier bodies after ``tier:`` (T0 lowest authority → T3 highest).
TIER_AUTHORITY_ORDER: tuple[str, ...] = ("T0", "T1", "T2", "T3")

# Balanced defaults (#1425): True = human approval required for this gate (#1432).
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
    # Fixed human-only controls: always require human approval (immutable).
    "gate_label_downgrade": True,
    "project_budget": True,
    "license": True,
}

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


def parse_pending_write_record(raw: str | None) -> dict[str, Any] | None:
    """Parse marker ``pending_write`` JSON: ``transition_id``, ``added``, ``removed``.

    Returns None if *raw* is not a well-formed record (no substring heuristics).
    """
    if not raw or not str(raw).strip():
        return None
    try:
        import json as _json

        data = _json.loads(str(raw).strip())
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    tid = data.get("transition_id")
    if not isinstance(tid, str) or not tid.strip():
        return None
    added = data.get("added", [])
    removed = data.get("removed", [])
    if not isinstance(added, list) or not isinstance(removed, list):
        return None
    if not all(isinstance(x, str) and x.strip() for x in added):
        return None
    if not all(isinstance(x, str) and x.strip() for x in removed):
        return None
    return {"transition_id": tid.strip(), "added": added, "removed": removed}


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


def _prefix_from_convention(prefixes: Any, key: str, fallback: str) -> str:
    if isinstance(prefixes, dict):
        raw = prefixes.get(key)
        if isinstance(raw, str) and raw.strip():
            p = raw.strip()
            return p if p.endswith(":") else p + ":"
    return fallback


def resolve_taxonomy_config(
    *,
    process_yaml_root: Mapping[str, Any] | None,
    lifecycle_block: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Merge canonical ``lifecycle.taxonomy`` (PR #1432) with defaults.

    Expected keys in YAML: ``type_labels``, ``prefixes``, ``tier_prefix`` referencing
    ``labels.issue_type_labels`` / ``labels.prefix_convention`` in ``process.yml``.
    Unknown keys are ignored.
    """
    labels_cfg: dict[str, Any] = {}
    if isinstance(process_yaml_root, dict):
        lc = process_yaml_root.get("labels")
        if isinstance(lc, dict):
            labels_cfg = lc

    issue_types: list[str] = []
    it = labels_cfg.get("issue_type_labels")
    if isinstance(it, dict):
        req = it.get("required_exactly_one")
        if isinstance(req, list):
            issue_types = [str(x).strip() for x in req if isinstance(x, str) and str(x).strip()]

    prefixes_map = labels_cfg.get("prefix_convention")
    risk_p = _prefix_from_convention(prefixes_map, "risk", "risk:")
    need_p = _prefix_from_convention(prefixes_map, "need", "need:")
    tier_p = "tier:"

    tax: dict[str, Any] = {
        "issue_type_labels": list(issue_types),
        "risk_prefix": risk_p,
        "need_prefix": need_p,
        "tier_prefix": tier_p,
    }

    lt = lifecycle_block.get("taxonomy") if isinstance(lifecycle_block, dict) else None
    if isinstance(lt, dict):
        tl_ref = lt.get("type_labels")
        if tl_ref == "labels.issue_type_labels" and issue_types:
            tax["issue_type_labels"] = list(issue_types)
        elif isinstance(tl_ref, list):
            tax["issue_type_labels"] = [str(x).strip() for x in tl_ref if isinstance(x, str) and str(x).strip()]

        pref_ref = lt.get("prefixes")
        if pref_ref == "labels.prefix_convention":
            tax["risk_prefix"] = risk_p
            tax["need_prefix"] = need_p
        elif isinstance(pref_ref, dict):
            tax["risk_prefix"] = _prefix_from_convention(pref_ref, "risk", tax["risk_prefix"])
            tax["need_prefix"] = _prefix_from_convention(pref_ref, "need", tax["need_prefix"])

        tp = lt.get("tier_prefix")
        if isinstance(tp, str) and tp.strip():
            tps = tp.strip()
            tax["tier_prefix"] = tps if tps.endswith(":") else tps + ":"

    return tax


def _value_after_prefix(label: str, prefix: str) -> str | None:
    ln = _normalize_label(label)
    p = prefix if prefix.endswith(":") else prefix + ":"
    if len(ln) <= len(p) or ln[: len(p)].lower() != p.lower():
        return None
    return ln[len(p) :].strip()


def _labels_with_unknown_prefix_bodies(
    labels: Sequence[str],
    prefix: str,
    known: set[str],
) -> bool:
    p = prefix if prefix.endswith(":") else prefix + ":"
    for lab in labels:
        if not _normalize_label(lab):
            continue
        body = _value_after_prefix(lab, p)
        if body is None:
            continue
        if body not in known:
            return True
    return False


def _labels_with_prefix(labels: Iterable[str], prefix: str) -> list[str]:
    p = prefix.lower()
    if not p.endswith(":"):
        p = p + ":"
    return [x for x in labels if _normalize_label(x).lower().startswith(p)]


def effective_risk_level(
    labels: Sequence[str],
    *,
    process_yaml_root: Mapping[str, Any] | None = None,
    lifecycle_block: Mapping[str, Any] | None = None,
) -> str | None:
    """Highest mapped ``risk`` severity, or None if absent or unmapped bodies exist."""
    tax = resolve_taxonomy_config(
        process_yaml_root=process_yaml_root,
        lifecycle_block=lifecycle_block,
    )
    rp = str(tax["risk_prefix"])
    known = set(RISK_SEVERITY_ORDER)
    norm = [_normalize_label(x) for x in labels if _normalize_label(x)]
    if _labels_with_unknown_prefix_bodies(norm, rp, known):
        return None
    values: list[str] = []
    for lab in norm:
        v = _value_after_prefix(lab, rp)
        if v is None:
            continue
        vl = v.lower()
        if vl not in RISK_SEVERITY_ORDER:
            return None
        values.append(vl)
    if not values:
        return None
    return max(values, key=lambda x: RISK_SEVERITY_ORDER.index(x))


def effective_tier_authority(
    labels: Sequence[str],
    *,
    process_yaml_root: Mapping[str, Any] | None = None,
    lifecycle_block: Mapping[str, Any] | None = None,
) -> str | None:
    """Highest ``tier`` authority (T0<T1<T2<T3), or None if absent or ambiguous/unmapped."""
    tax = resolve_taxonomy_config(
        process_yaml_root=process_yaml_root,
        lifecycle_block=lifecycle_block,
    )
    tp = str(tax["tier_prefix"])
    known = set(TIER_AUTHORITY_ORDER)
    norm = [_normalize_label(x) for x in labels if _normalize_label(x)]
    tiers = _labels_with_prefix(norm, tp)
    if len(tiers) != 1:
        return None
    body = _value_after_prefix(tiers[0], tp)
    if body is None:
        return None
    if body not in known:
        return None
    return body


def label_change_is_approver_only_downgrade(
    prev_labels: Sequence[str],
    new_labels: Sequence[str],
    *,
    process_yaml_root: Mapping[str, Any] | None = None,
    lifecycle_block: Mapping[str, Any] | None = None,
) -> tuple[bool, list[str]]:
    """True when effective risk/tier drops or protected need:* labels are removed (#1425).

    Replacing ``risk:low`` with ``risk:critical`` is **not** a downgrade (effective risk rises).
    Lowering ``tier:T3`` → ``tier:T2`` **is** a downgrade (authority drop).
    """
    tax = resolve_taxonomy_config(
        process_yaml_root=process_yaml_root,
        lifecycle_block=lifecycle_block,
    )
    need_hp = str(tax["need_prefix"])
    human_lab = f"{need_hp}human-review".lower()
    sec_lab = f"{need_hp}security-review".lower()

    prev_norm = [_normalize_label(x) for x in prev_labels if _normalize_label(x)]
    new_norm = [_normalize_label(x) for x in new_labels if _normalize_label(x)]
    prev_set = set(prev_norm)
    new_set = set(new_norm)
    removed = prev_set - new_set

    reasons: list[str] = []

    prev_risk = effective_risk_level(
        prev_norm, process_yaml_root=process_yaml_root, lifecycle_block=lifecycle_block
    )
    new_risk = effective_risk_level(
        new_norm, process_yaml_root=process_yaml_root, lifecycle_block=lifecycle_block
    )
    if prev_risk is None and new_risk is None:
        pass  # only non-risk or unknown risk labels
    elif prev_risk is None or new_risk is None:
        if new_risk is None and prev_risk is not None:
            reasons.append("risk_cleared")
    else:
        if RISK_SEVERITY_ORDER.index(new_risk) < RISK_SEVERITY_ORDER.index(prev_risk):
            reasons.append(f"risk_downgrade:{prev_risk}->{new_risk}")

    prev_tier = effective_tier_authority(
        prev_norm, process_yaml_root=process_yaml_root, lifecycle_block=lifecycle_block
    )
    new_tier = effective_tier_authority(
        new_norm, process_yaml_root=process_yaml_root, lifecycle_block=lifecycle_block
    )
    if prev_tier is not None and new_tier is None:
        tp = str(tax["tier_prefix"])
        prev_tiers = _labels_with_prefix(prev_norm, tp)
        if prev_tiers and not _labels_with_prefix(new_norm, tp):
            reasons.append(f"tier_removed:{prev_tiers[0]}")
    elif prev_tier is not None and new_tier is not None:
        if TIER_AUTHORITY_ORDER.index(new_tier) < TIER_AUTHORITY_ORDER.index(prev_tier):
            reasons.append(f"tier_downgrade:{prev_tier}->{new_tier}")

    for lab in removed:
        low = lab.lower()
        if low in (human_lab, sec_lab):
            reasons.append(f"removed:{lab}")

    return bool(reasons), reasons


def label_indicates_critical_raise(
    prev_labels: Sequence[str],
    new_labels: Sequence[str],
    *,
    process_yaml_root: Mapping[str, Any] | None = None,
    lifecycle_block: Mapping[str, Any] | None = None,
) -> tuple[bool, bool]:
    """Transition to effective risk *critical* from a lower level."""
    prev = effective_risk_level(
        [_normalize_label(x) for x in prev_labels if _normalize_label(x)],
        process_yaml_root=process_yaml_root,
        lifecycle_block=lifecycle_block,
    )
    new = effective_risk_level(
        [_normalize_label(x) for x in new_labels if _normalize_label(x)],
        process_yaml_root=process_yaml_root,
        lifecycle_block=lifecycle_block,
    )
    already = prev == "critical"
    raised = new == "critical" and not already
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
    """True when this gate requires human approval (#1432: gate true → human required)."""
    g = dict(gates) if gates is not None else merged_lifecycle_gates(None)
    if key in ("gate_label_downgrade", "project_budget", "license"):
        return True
    return bool(g.get(key, False))


def stricter_autonomy_cap(
    *,
    gate_requires_human: bool,
    risk_tolerance: str | None,
    action_needs_min_tolerance: str = "medium",
) -> tuple[bool, str]:
    """Apply lifecycle gate first, then cap by ``autonomy.risk_tolerance`` (stricter wins).

    ``gate_requires_human`` is the result of ``gate_requires_human_review(...)`` for the action.
    """
    if gate_requires_human:
        return False, "lifecycle gate requires human approval"
    need = risk_tolerance_rank(action_needs_min_tolerance)
    have = risk_tolerance_rank(risk_tolerance)
    if have < need:
        return False, f"risk_tolerance caps action (have {have}, need {need})"
    return True, "ok"


class TaxonomyMatchResult:
    __slots__ = ("ok", "reason")

    def __init__(self, ok: bool, reason: str = "") -> None:
        self.ok = ok
        self.reason = reason


def match_labels_by_taxonomy(
    labels: Iterable[str],
    *,
    risk: str | None = None,
    tier: str | None = None,
    issue_type: str | None = None,
    process_yaml_root: Mapping[str, Any] | None = None,
    lifecycle_block: Mapping[str, Any] | None = None,
) -> TaxonomyMatchResult:
    """Match issue labels using ``lifecycle.taxonomy`` + ``labels`` from process.yml (#1432)."""
    norm = [_normalize_label(x) for x in labels if _normalize_label(x)]
    tax = resolve_taxonomy_config(
        process_yaml_root=process_yaml_root,
        lifecycle_block=lifecycle_block,
    )

    if risk is not None:
        rp = str(tax["risk_prefix"])
        expected = f"{rp}{risk}" if rp.endswith(":") else f"{rp}:{risk}"
        if not any(_normalize_label(x).lower() == expected.lower() for x in norm):
            risky = _labels_with_prefix(norm, rp)
            if risky:
                return TaxonomyMatchResult(False, "risk label present but does not match requested value")
            return TaxonomyMatchResult(False, "expected risk label missing")

    if tier is not None:
        tp = str(tax["tier_prefix"])
        expected = f"{tp}{tier}" if tp.endswith(":") else f"{tp}:{tier}"
        if not any(_normalize_label(x).lower() == expected.lower() for x in norm):
            tiers = _labels_with_prefix(norm, tp)
            if tiers:
                return TaxonomyMatchResult(False, "tier label present but does not match requested value")
            return TaxonomyMatchResult(False, "expected tier label missing")

    if issue_type is not None:
        allowed = tax.get("issue_type_labels")
        if not isinstance(allowed, list) or not allowed:
            return TaxonomyMatchResult(False, "issue type labels not resolved from process.yml")
        if issue_type not in allowed:
            return TaxonomyMatchResult(False, "requested issue type not in configured taxonomy")
        if issue_type not in norm:
            return TaxonomyMatchResult(False, "issue type label missing")

    return TaxonomyMatchResult(True, "")


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


def read_process_yaml_root(repo_root: Path) -> dict[str, Any] | None:
    """Load ``.agentic/process.yml`` root mapping, or None if missing.

    Raises ``ValueError`` when the file exists but the document root is not a mapping.
    """
    path = repo_root / PROCESS_REL
    if not path.is_file():
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"invalid YAML in {PROCESS_REL}: {exc}") from exc
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(".agentic/process.yml root must be a mapping")
    return data


def extract_lifecycle_value(root_data: dict[str, Any] | None) -> Any:
    """Return raw ``lifecycle`` value: use ``_SENTINEL`` if key absent."""
    if root_data is None:
        return _SENTINEL
    if "lifecycle" not in root_data:
        return _SENTINEL
    return root_data.get("lifecycle")


def normalize_lifecycle_block(
    lifecycle_raw: Any,
) -> tuple[dict[str, Any] | None, str | None]:
    """Return (block_dict, error). None block + error means fail closed."""
    if lifecycle_raw is _SENTINEL:
        return {}, None
    if lifecycle_raw is None:
        return None, "lifecycle is explicitly null"
    if not isinstance(lifecycle_raw, dict):
        return None, "lifecycle must be a mapping"
    return lifecycle_raw, None


def read_lifecycle_block(repo_root: Path) -> dict[str, Any]:
    """Return the ``lifecycle`` mapping when valid; ``{{}}`` if key absent; raise on null/malformed."""

    root = read_process_yaml_root(repo_root)
    if root is None:
        return {}
    raw = extract_lifecycle_value(root)
    block, err = normalize_lifecycle_block(raw)
    if err:
        raise ValueError(err)
    return block or {}


def read_lifecycle_block_for_init_merge(
    repo_root: Path,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Return ``(lifecycle_block | None, full_process_root | None)`` for init merge."""
    root = read_process_yaml_root(repo_root)
    if root is None:
        return None, None
    raw = extract_lifecycle_value(root)
    if raw is _SENTINEL:
        return {}, root
    block, err = normalize_lifecycle_block(raw)
    if err:
        raise ValueError(f"{err} (.agentic/process.yml)")
    return dict(block or {}), root


def parse_lifecycle_approvers_list(raw: Any) -> tuple[str, ...] | None:
    """Return normalized logins, None if key absent, () only via explicit empty list."""
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
    lifecycle_block: Mapping[str, Any] | None,
    lifecycle_parse_error: str | None,
    repo_obj: Mapping[str, Any] | None,
) -> ResolvedApprovers:
    """Resolve effective approver set (fail closed when unset or invalid)."""
    if lifecycle_parse_error:
        return ResolvedApprovers((), "none", True, lifecycle_parse_error)

    life: dict[str, Any] = dict(lifecycle_block or {})

    if "approvers" not in life:
        raw: Any = _SENTINEL
    else:
        raw = life.get("approvers")

    org = bool(repo_obj.get("owner", {}).get("type") == "Organization") if isinstance(
        repo_obj, dict
    ) else False

    if raw is _SENTINEL:
        if org:
            return ResolvedApprovers((), "none", True, "org repo requires explicit lifecycle.approvers")
        owner = _owner_login_from_repo(repo_obj)
        if not owner:
            return ResolvedApprovers((), "none", True, "cannot resolve repo owner for approver fallback")
        return ResolvedApprovers((owner.lower(),), "owner_fallback", False, "")

    if raw is None:
        return ResolvedApprovers((), "none", True, "lifecycle.approvers is explicitly null")

    try:
        approvers = parse_lifecycle_approvers_list(raw)
    except ValueError as exc:
        return ResolvedApprovers((), "none", True, str(exc))

    assert approvers is not None
    if len(approvers) == 0:
        return ResolvedApprovers((), "explicit_config", True, "empty lifecycle.approvers")

    return ResolvedApprovers(approvers, "explicit_config", False, "")


def resolve_runtime_approvers_from_repo_yaml(
    repo_root: Path | None,
    *,
    repo_obj: Mapping[str, Any] | None,
) -> ResolvedApprovers:
    """Load process.yml from disk and resolve approvers (null/malformed fail closed)."""
    root = Path(repo_root) if repo_root is not None else Path(".")
    data = read_process_yaml_root(root)
    if data is None:
        return resolve_runtime_approvers(
            lifecycle_block={},
            lifecycle_parse_error=None,
            repo_obj=repo_obj,
        )
    raw_life = extract_lifecycle_value(data)
    if raw_life is _SENTINEL:
        block: dict[str, Any] | None = {}
        err = None
    else:
        block, err = normalize_lifecycle_block(raw_life)
    return resolve_runtime_approvers(
        lifecycle_block=block,
        lifecycle_parse_error=err,
        repo_obj=repo_obj,
    )


def is_approver(
    actor_login: str | None,
    resolved: ResolvedApprovers,
) -> bool:
    if resolved.refuse_all or not actor_login:
        return False
    return actor_login.strip().lower() in resolved.logins


def _merge_gates_preserve_stricter(existing: dict[str, bool], defaults: dict[str, bool]) -> dict[str, bool]:
    """Preserve configured gates; add defaults only for keys that are absent."""
    out = {k: bool(v) for k, v in existing.items()}
    for k, dflt in defaults.items():
        if k not in out:
            out[k] = bool(dflt)
    return out


def plan_init_process_yaml(
    *,
    token_user_login: str,
    repo_obj: Mapping[str, Any] | None,
    org_approvers: Sequence[str] | None,
    explicit_user_approvers: Sequence[str] | None = None,
    confirm_non_owner_for_default: bool = False,
    confirm_non_owner_for_explicit_approvers: bool = False,
    existing_lifecycle: Mapping[str, Any] | None = None,
    process_yaml_root: Mapping[str, Any] | None = None,
    force_lifecycle: bool = False,
) -> dict[str, Any]:
    """Build ``lifecycle`` fragment for merge into ``.agentic/process.yml``.

    Preserves existing non-empty ``approvers`` and stricter ``gates`` unless
    ``force_lifecycle`` is true.
    """
    tu = token_user_login.strip().lower()
    if not tu:
        raise ValueError("token_user_login is required")

    prior = dict(existing_lifecycle or {})
    prior_gates = prior.get("gates")

    org = bool(repo_obj and repo_obj.get("owner", {}).get("type") == "Organization")

    new_block: dict[str, Any] = {}

    if not force_lifecycle and prior.get("approvers") is None and "approvers" in prior:
        raise ValueError("lifecycle.approvers is null; remove the key or set a non-null list")

    if not force_lifecycle and "approvers" in prior:
        new_block["approvers"] = copy.deepcopy(prior["approvers"])
    else:
        if org:
            if not org_approvers:
                raise ValueError("organization repository requires explicit approvers")
            apps = [a.strip().lower() for a in org_approvers if isinstance(a, str) and a.strip()]
            if not apps:
                raise ValueError("organization approvers list is empty")
            new_block["approvers"] = apps
        elif explicit_user_approvers:
            apps = [a.strip().lower() for a in explicit_user_approvers if isinstance(a, str) and a.strip()]
            if not apps:
                raise ValueError("explicit user approvers list is empty")
            owner = _owner_login_from_repo(repo_obj)
            if owner is None:
                raise ValueError("cannot read owner.login from repo object")
            if tu != owner.lower() and not confirm_non_owner_for_explicit_approvers:
                raise ValueError(
                    "token user does not match repo owner.login; re-run with confirm_non_owner"
                )
            new_block["approvers"] = apps
        else:
            owner = _owner_login_from_repo(repo_obj)
            if owner is None:
                raise ValueError("cannot read owner.login from repo object")
            owner_l = owner.lower()
            if tu != owner_l and not confirm_non_owner_for_default:
                raise ValueError(
                    "token user does not match repo owner.login; re-run with confirm_non_owner"
                )
            new_block["approvers"] = [tu]

    if force_lifecycle or prior_gates is None:
        merged_gates = dict(DEFAULT_LIFECYCLE_GATES)
    elif isinstance(prior_gates, dict):
        merged_gates = _merge_gates_preserve_stricter(
            {k: bool(v) for k, v in prior_gates.items()},
            DEFAULT_LIFECYCLE_GATES,
        )
    else:
        merged_gates = dict(DEFAULT_LIFECYCLE_GATES)
    new_block["gates"] = merged_gates

    if not force_lifecycle and "taxonomy" in prior:
        new_block["taxonomy"] = copy.deepcopy(prior["taxonomy"])
    elif not force_lifecycle:
        new_block["taxonomy"] = {
            "type_labels": "labels.issue_type_labels",
            "prefixes": "labels.prefix_convention",
            "tier_prefix": "tier:",
        }
    elif "taxonomy" in prior:
        new_block["taxonomy"] = copy.deepcopy(prior["taxonomy"])
    else:
        new_block["taxonomy"] = {
            "type_labels": "labels.issue_type_labels",
            "prefixes": "labels.prefix_convention",
            "tier_prefix": "tier:",
        }
    if process_yaml_root is not None:
        resolve_taxonomy_config(
            process_yaml_root=process_yaml_root,
            lifecycle_block=new_block,
        )

    return {"lifecycle": new_block}


def apply_lifecycle_fragment(existing: dict[str, Any], fragment: dict[str, Any]) -> dict[str, Any]:
    """Deep-merge mappings from *fragment* into a copy of *existing* (YAML root)."""

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
        current = read_process_yaml_root(repo_root)
        if current is None:
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
    process_yaml_root: Mapping[str, Any] | None = None,
    lifecycle_block: Mapping[str, Any] | None = None,
) -> ShadowLabelChangeDecision:
    """Fail-closed policy for shadow simulation (#1425; no GitHub writes)."""
    actor = (actor_login or "").strip().lower()

    downgrade, removed = label_change_is_approver_only_downgrade(
        prev_labels,
        new_labels,
        process_yaml_root=process_yaml_root,
        lifecycle_block=lifecycle_block,
    )
    if downgrade:
        if is_approver(actor, resolved):
            return ShadowLabelChangeDecision(True, "downgrade_ok_approver", ())
        return ShadowLabelChangeDecision(
            False,
            "downgrade_reverted",
            (f"change requires approver: {', '.join(removed)}",),
        )

    raised, _already = label_indicates_critical_raise(
        prev_labels,
        new_labels,
        process_yaml_root=process_yaml_root,
        lifecycle_block=lifecycle_block,
    )
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
    pending_write_record_json: str | None = None,
) -> ShadowApprovalCommandDecision:
    """First-line-only /plate resume|approve; approver-only; pending_write blocks."""
    first = parse_first_line(comment_body)
    cmd = parse_plate_approval_command(first)
    if cmd is None:
        return ShadowApprovalCommandDecision(False, "not_approval_command", ())

    rec = parse_pending_write_record(pending_write_record_json)
    if rec is not None:
        return ShadowApprovalCommandDecision(
            False,
            "pending_write",
            (f"pending_write transition_id={rec['transition_id']}",),
        )

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
