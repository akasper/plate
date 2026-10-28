"""Watcher guards for ``gh plate pr babysit --watch`` (#1233, #1246).

Ideas adapted from t3dotgg/tstack ``pr-wait`` (MIT, Theo Browne); implementation
and wording are PLATE-original. Parent cost model: #1077 (ETag probes, backoff,
delta wakes — no tight polling loops).
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Protocol

from .github_client import GhApiError, GhClient

EVENT_MEMORY_MAX_AGE_SECONDS = 6 * 3600

_REPO_RE = re.compile(r"^([^/]+)/([^/]+)$")


def _split_repo(repo: str) -> tuple[str, str]:
    m = _REPO_RE.match(repo.strip())
    if not m:
        raise ValueError(f"repo must be owner/name, got: {repo!r}")
    return m.group(1), m.group(2)


class HttpGet(Protocol):
    def get(self, path: str, headers: Mapping[str, str] | None = None) -> tuple[int, dict[str, str], Any]:
        ...


def is_graphql_rate_limited(exc: BaseException) -> bool:
    """True when ``exc`` looks like GraphQL primary rate limit exhaustion."""
    if not isinstance(exc, GhApiError):
        return False
    lower = str(exc).lower()
    if "graphql" in lower and "rate limit" in lower:
        return True
    if "rate limit" in lower and "403" in lower:
        return True
    return "rate limit" in lower and "api rate limit" in lower


def _safe_json_get(http: HttpGet, path: str) -> Any | None:
    try:
        status, _, body = http.get(path, None)
    except (KeyError, GhApiError, RuntimeError):
        return None
    if status in (404, 403):
        return None
    if status >= 400:
        return None
    return body


def _contexts_from_branch_protection(body: Mapping[str, Any] | None) -> set[str]:
    if not isinstance(body, dict):
        return set()
    block = body.get("required_status_checks") or {}
    if not isinstance(block, dict):
        return set()
    raw = block.get("contexts") or []
    if not isinstance(raw, list):
        return set()
    return {str(item).strip() for item in raw if str(item).strip()}


def _contexts_from_ruleset_detail(body: Mapping[str, Any] | None) -> set[str]:
    if not isinstance(body, dict):
        return set()
    out: set[str] = set()
    rules = body.get("rules") or []
    if not isinstance(rules, list):
        return out
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        if str(rule.get("type") or "") != "required_status_checks":
            continue
        params = rule.get("parameters") or {}
        if not isinstance(params, dict):
            continue
        checks = params.get("required_status_checks") or params.get("checks") or []
        if isinstance(checks, list):
            for item in checks:
                if isinstance(item, dict):
                    ctx = item.get("context") or item.get("name")
                    if ctx:
                        out.add(str(ctx).strip())
                elif item:
                    out.add(str(item).strip())
    return out


def _ref_name_matches(base_ref: str, pattern: str) -> bool:
    """True when ``pattern`` matches branch ``base_ref`` (GitHub ruleset ref_name rules)."""
    pat = str(pattern).strip()
    if not pat:
        return False
    if pat == "~ALL":
        return True
    if pat == "~DEFAULT_BRANCH":
        return False
    branch = base_ref.removeprefix("refs/heads/")
    candidates = {branch, f"refs/heads/{branch}"}
    if pat.startswith("refs/heads/"):
        return any(fnmatch.fnmatch(candidate, pat) for candidate in candidates)
    return fnmatch.fnmatch(branch, pat) or fnmatch.fnmatch(f"refs/heads/{branch}", f"refs/heads/{pat}")


def _ruleset_applies_to_base_ref(meta: Mapping[str, Any], detail: Mapping[str, Any] | None, base_ref: str) -> bool:
    """Only active-enforcement branch rulesets whose ref conditions include ``base_ref``."""
    enforcement = str(meta.get("enforcement") or "").lower()
    if enforcement != "active":
        return False
    source = detail if isinstance(detail, dict) else meta
    target = str(source.get("target") or meta.get("target") or "").lower()
    if target and target != "branch":
        return False
    conditions = source.get("conditions") if isinstance(source, dict) else None
    if not isinstance(conditions, dict):
        return False
    ref_name = conditions.get("ref_name")
    if not isinstance(ref_name, dict):
        return False
    includes = ref_name.get("include") or []
    if not isinstance(includes, list) or not includes:
        return False
    excludes = ref_name.get("exclude") or []
    if isinstance(excludes, list):
        for pattern in excludes:
            if _ref_name_matches(base_ref, str(pattern)):
                return False
    return any(_ref_name_matches(base_ref, str(pattern)) for pattern in includes)


def fetch_required_check_contexts(
    http: HttpGet,
    repo: str,
    base_ref: str | None,
) -> frozenset[str]:
    """Required status contexts from branch protection and repository rulesets."""
    if not base_ref:
        return frozenset()
    owner, name = _split_repo(repo)
    contexts: set[str] = set()
    protection = _safe_json_get(http, f"/repos/{owner}/{name}/branches/{base_ref}/protection")
    contexts |= _contexts_from_branch_protection(protection if isinstance(protection, dict) else None)

    rulesets = _safe_json_get(http, f"/repos/{owner}/{name}/rulesets?per_page=100")
    if isinstance(rulesets, list):
        for meta in rulesets:
            if not isinstance(meta, dict):
                continue
            if str(meta.get("enforcement") or "").lower() != "active":
                continue
            ruleset_id = meta.get("id")
            if ruleset_id is None:
                continue
            detail = _safe_json_get(http, f"/repos/{owner}/{name}/rulesets/{ruleset_id}")
            if not _ruleset_applies_to_base_ref(meta, detail if isinstance(detail, dict) else None, base_ref):
                continue
            contexts |= _contexts_from_ruleset_detail(detail if isinstance(detail, dict) else None)
    return frozenset(contexts)


def observed_check_contexts(
    status_json: Mapping[str, Any] | None,
    check_runs: list[dict[str, Any]],
) -> set[str]:
    """Context names seen on the head commit (status API + check runs)."""
    seen: set[str] = set()
    if isinstance(status_json, dict):
        for item in status_json.get("statuses") or []:
            if isinstance(item, dict):
                ctx = item.get("context")
                if ctx:
                    seen.add(str(ctx).strip())
    for run in check_runs:
        if not isinstance(run, dict):
            continue
        name = run.get("name") or run.get("app", {}).get("slug")
        if name:
            seen.add(str(name).strip())
    return seen


def missing_required_contexts(required: frozenset[str], observed: set[str]) -> list[str]:
    if not required:
        return []
    observed_lower = {value.lower() for value in observed}
    missing = [ctx for ctx in sorted(required) if ctx.lower() not in observed_lower]
    return missing


def compute_raw_ci_state(
    status_json: Mapping[str, Any] | None,
    check_runs: list[dict[str, Any]],
    *,
    missing_required: list[str],
) -> str | None:
    """Aggregate CI state before settle/required guards."""
    if missing_required:
        return "pending"
    status_state = None
    if isinstance(status_json, dict):
        total_count = status_json.get("total_count")
        if total_count != 0:
            status_state = status_json.get("state")
    check_states = [
        "pending"
        if str(run.get("status") or "").lower() != "completed"
        else str(run.get("conclusion") or "").lower()
        for run in check_runs
        if isinstance(run, dict)
    ]
    if "pending" in check_states or str(status_state or "").lower() in ("pending", "expected"):
        return "pending"
    if any(
        value in ("failure", "timed_out", "cancelled", "action_required", "startup_failure")
        for value in check_states
    ):
        return "failure"
    if str(status_state or "").lower() in ("failure", "error"):
        return str(status_state).lower()
    if status_state or check_states:
        return "success"
    return None


def ci_read_fingerprint(
    status_json: Mapping[str, Any] | None,
    check_runs: list[dict[str, Any]],
    *,
    missing_required: list[str],
    head_sha: str | None = None,
) -> str:
    """Stable fingerprint of the current CI observation (for settle guard)."""
    parts: list[str] = []
    if head_sha:
        parts.append(f"head:{head_sha}")
    if missing_required:
        parts.append("missing:" + ",".join(missing_required))
    if isinstance(status_json, dict):
        total_count = status_json.get("total_count")
        if total_count != 0:
            parts.append(f"status:{status_json.get('state')}")
        for item in status_json.get("statuses") or []:
            if isinstance(item, dict):
                parts.append(
                    f"s:{item.get('context')}:{item.get('state')}"
                )
    for run in sorted(check_runs, key=lambda r: str(r.get("name") or "")):
        if not isinstance(run, dict):
            continue
        parts.append(
            f"r:{run.get('name')}:{run.get('status')}:{run.get('conclusion')}"
        )
    digest = hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()
    return digest[:16]


def apply_settle_before_finished(
    raw_ci_state: str | None,
    fingerprint: str,
    *,
    prior_fingerprint: str | None,
    prior_streak: int,
    prior_ci_state: str | None = None,
) -> tuple[str | None, str | None, int]:
    """Report CI success only after two consecutive identical reads (#1233 guard 2).

    Preserves legacy probe behavior: an already-reported ``success`` stays success on
    unchanged reads (304), and transitions from ``pending``/``failure`` report success
    immediately. The settle deferral applies only on the first CI observation when
    there was no prior ``ci_state`` (fresh probe / first tick).
    """
    streak = prior_streak
    if fingerprint != prior_fingerprint:
        streak = 1
    else:
        streak = prior_streak + 1

    if raw_ci_state == "success":
        if prior_ci_state == "success":
            return "success", fingerprint, streak
        if prior_ci_state in ("pending", "failure"):
            return "success", fingerprint, streak
        if prior_ci_state is None:
            return "pending", fingerprint, streak
        if streak >= 2:
            return "success", fingerprint, streak
        return "pending", fingerprint, streak

    return raw_ci_state, fingerprint, 0


def apply_ci_guards_to_probe(
    *,
    status_json: Mapping[str, Any] | None,
    check_runs: list[dict[str, Any]],
    required_contexts: frozenset[str],
    prior_fingerprint: str | None,
    prior_streak: int,
    prior_ci_state: str | None = None,
    head_sha: str | None = None,
) -> tuple[str | None, str | None, int]:
    """Combine required-check and settle guards for one probe tick."""
    missing = missing_required_contexts(
        required_contexts,
        observed_check_contexts(status_json, check_runs),
    )
    raw = compute_raw_ci_state(status_json, check_runs, missing_required=missing)
    fingerprint = ci_read_fingerprint(
        status_json, check_runs, missing_required=missing, head_sha=head_sha
    )
    return apply_settle_before_finished(
        raw,
        fingerprint,
        prior_fingerprint=prior_fingerprint,
        prior_streak=prior_streak,
        prior_ci_state=prior_ci_state,
    )


def _mergeable_to_graphql(mergeable_state: str | None) -> str:
    mapping = {
        "clean": "CLEAN",
        "dirty": "DIRTY",
        "blocked": "BLOCKED",
        "behind": "BEHIND",
        "unstable": "UNSTABLE",
        "draft": "DRAFT",
    }
    key = str(mergeable_state or "").lower()
    return mapping.get(key, "UNKNOWN")


def _rollup_from_rest(
    status_json: Mapping[str, Any] | None,
    check_runs: list[dict[str, Any]],
    *,
    missing_required: list[str],
) -> dict[str, Any]:
    raw = compute_raw_ci_state(status_json, check_runs, missing_required=missing_required)
    state = str(raw or "pending").upper()
    nodes: list[dict[str, Any]] = []
    if isinstance(status_json, dict):
        for item in status_json.get("statuses") or []:
            if isinstance(item, dict):
                nodes.append(
                    {
                        "context": item.get("context"),
                        "state": str(item.get("state") or "").upper(),
                    }
                )
    for run in check_runs:
        if not isinstance(run, dict):
            continue
        nodes.append(
            {
                "name": run.get("name"),
                "status": str(run.get("status") or "").upper(),
                "conclusion": str(run.get("conclusion") or "").upper(),
            }
        )
    return {"state": state, "contexts": {"nodes": nodes}}


def review_decision_from_rest_reviews(reviews: list[dict[str, Any]]) -> str | None:
    """Aggregate review decision from paginated REST reviews (per-reviewer latest state)."""
    by_user: dict[str, str] = {}
    ordered = sorted(
        (item for item in reviews if isinstance(item, dict)),
        key=lambda item: (str(item.get("submitted_at") or ""), int(item.get("id") or 0)),
    )
    for review in ordered:
        user = (review.get("user") or {}).get("login")
        if not user:
            continue
        state = str(review.get("state") or "").upper()
        if state == "DISMISSED":
            by_user.pop(str(user), None)
            continue
        if state in ("APPROVED", "CHANGES_REQUESTED", "COMMENTED", "PENDING"):
            by_user[str(user)] = state
    if any(value == "CHANGES_REQUESTED" for value in by_user.values()):
        return "CHANGES_REQUESTED"
    if any(value == "APPROVED" for value in by_user.values()):
        return "APPROVED"
    return None


def load_pr_data_rest_fallback(client: GhClient, repo: str, pr_number: int) -> dict[str, Any]:
    """GraphQL fallback: load PR merge/check snapshot via REST (#1233 guard 5)."""
    owner, name = _split_repo(repo)
    pull = client.api(f"repos/{owner}/{name}/pulls/{pr_number}") or {}
    head_sha = (pull.get("head") or {}).get("sha")
    base_ref = (pull.get("base") or {}).get("ref")
    mergeable_state = pull.get("mergeable_state")
    status_json: dict[str, Any] = {}
    check_runs: list[dict[str, Any]] = []
    if head_sha:
        status_json = client.api(f"repos/{owner}/{name}/commits/{head_sha}/status") or {}
        page = 1
        while True:
            payload = client.api(
                f"repos/{owner}/{name}/commits/{head_sha}/check-runs",
                fields={"per_page": 100, "page": page},
            )
            runs = payload.get("check_runs", []) if isinstance(payload, dict) else []
            if not isinstance(runs, list):
                break
            check_runs.extend(run for run in runs if isinstance(run, dict))
            if len(runs) < 100:
                break
            page += 1

    class _GhHttp:
        def get(self, path: str, headers=None):
            endpoint = path.lstrip("/")
            if endpoint.startswith("repos/"):
                body = client.api(endpoint)
                return 200, {}, body
            raise RuntimeError(path)

    required = fetch_required_check_contexts(_GhHttp(), repo, base_ref)
    missing = missing_required_contexts(required, observed_check_contexts(status_json, check_runs))
    rollup = _rollup_from_rest(status_json, check_runs, missing_required=missing)

    review_decision = None
    try:
        reviews: list[dict[str, Any]] = []
        page = 1
        while True:
            batch = (
                client.api(
                    f"repos/{owner}/{name}/pulls/{pr_number}/reviews",
                    fields={"per_page": 100, "page": page},
                )
                or []
            )
            if not isinstance(batch, list) or not batch:
                break
            reviews.extend(item for item in batch if isinstance(item, dict))
            if len(batch) < 100:
                break
            page += 1
        review_decision = review_decision_from_rest_reviews(reviews)
    except GhApiError:
        review_decision = None

    return {
        "reviewThreads": [],
        "review_threads_unavailable": True,
        "mergeStateStatus": _mergeable_to_graphql(mergeable_state),
        "baseRefName": base_ref or "",
        "headRefName": (pull.get("head") or {}).get("ref") or "",
        "reviewDecision": review_decision,
        "statusCheckRollup": rollup,
        "rest_fallback": True,
    }


def atomic_write_json(path: Path | str, payload: Mapping[str, Any]) -> None:
    """Write JSON atomically (temp file + ``os.replace``) for Windows-safe persistence."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, target)


def _parse_github_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_z(when: datetime) -> str:
    return when.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def event_ledger_path(repo: str, pr: int, root: Path | str | None = None) -> Path:
    owner, name = _split_repo(repo)
    base = Path(root) if root is not None else Path.cwd()
    return base / ".agentic" / "babysit" / f"{len(owner)}-{owner}-{len(name)}-{name}-{pr}.events.json"


@dataclass
class EventLedger:
    """Restart-safe memory of watch events already surfaced to the operator."""

    reported: dict[str, str] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return {"reported": dict(sorted(self.reported.items()))}

    @classmethod
    def from_json(cls, data: Mapping[str, Any] | None) -> EventLedger:
        if not isinstance(data, dict):
            return cls()
        raw = data.get("reported") or {}
        if not isinstance(raw, dict):
            return cls()
        reported = {str(key): str(value) for key, value in raw.items()}
        return cls(reported=reported)


def load_event_ledger(path: Path | str) -> EventLedger:
    target = Path(path)
    if not target.is_file():
        return EventLedger()
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return EventLedger()
    return EventLedger.from_json(data)


def save_event_ledger(path: Path | str, ledger: EventLedger) -> None:
    atomic_write_json(Path(path), ledger.to_json())


def prune_event_ledger(
    ledger: EventLedger,
    *,
    now: datetime | None = None,
    max_age_seconds: int = EVENT_MEMORY_MAX_AGE_SECONDS,
) -> None:
    """Drop reported-event entries older than ``max_age_seconds`` (#1246 guard 4)."""
    now = now or _utc_now()
    cutoff = now - timedelta(seconds=max_age_seconds)
    kept: dict[str, str] = {}
    for key, reported_at in ledger.reported.items():
        ts = _parse_github_ts(reported_at)
        if ts is None or ts >= cutoff:
            kept[key] = reported_at
    ledger.reported = kept


def event_memory_catchup_since(last_checked_at: str | None, now: datetime | None = None) -> str:
    """Widen the REST ``since`` window on watch restart (at most six hours)."""
    now = now or _utc_now()
    floor = now - timedelta(seconds=EVENT_MEMORY_MAX_AGE_SECONDS)
    if not last_checked_at:
        return _iso_z(floor)
    last = _parse_github_ts(last_checked_at)
    if last is None:
        return _iso_z(floor)
    effective = max(last, floor)
    return _iso_z(effective)


def _event_key_issue_comment(item: Mapping[str, Any]) -> str:
    return f"issue_comment:{int(item.get('id') or 0)}"


def _event_key_review_comment(item: Mapping[str, Any]) -> str:
    return f"review_comment:{int(item.get('id') or 0)}"


def _event_key_review(item: Mapping[str, Any]) -> str:
    return f"review:{int(item.get('id') or 0)}"


def _event_created_at(item: Mapping[str, Any]) -> datetime | None:
    return _parse_github_ts(
        str(item.get("created_at") or item.get("submitted_at") or "")
    )


def _within_event_memory_window(
    item: Mapping[str, Any],
    *,
    now: datetime,
    max_age_seconds: int = EVENT_MEMORY_MAX_AGE_SECONDS,
) -> bool:
    created = _event_created_at(item)
    if created is None:
        return True
    return created >= now - timedelta(seconds=max_age_seconds)


def filter_delta_by_event_memory(
    delta: Mapping[str, Any],
    ledger: EventLedger,
    *,
    now: datetime | None = None,
    max_age_seconds: int = EVENT_MEMORY_MAX_AGE_SECONDS,
) -> dict[str, Any]:
    """Drop delta items already reported or too old to replay (#1246 guard 4)."""
    now = now or _utc_now()
    out = dict(delta)
    filtered_issue: list[dict[str, Any]] = []
    for item in delta.get("issue_comments") or []:
        if not isinstance(item, dict):
            continue
        key = _event_key_issue_comment(item)
        if key in ledger.reported:
            continue
        if not _within_event_memory_window(item, now=now, max_age_seconds=max_age_seconds):
            continue
        filtered_issue.append(item)
    filtered_review_comments: list[dict[str, Any]] = []
    for item in delta.get("review_comments") or []:
        if not isinstance(item, dict):
            continue
        key = _event_key_review_comment(item)
        if key in ledger.reported:
            continue
        if not _within_event_memory_window(item, now=now, max_age_seconds=max_age_seconds):
            continue
        filtered_review_comments.append(item)
    filtered_reviews: list[dict[str, Any]] = []
    for item in delta.get("reviews") or []:
        if not isinstance(item, dict):
            continue
        key = _event_key_review(item)
        if key in ledger.reported:
            continue
        if not _within_event_memory_window(item, now=now, max_age_seconds=max_age_seconds):
            continue
        filtered_reviews.append(item)
    out["issue_comments"] = filtered_issue
    out["review_comments"] = filtered_review_comments
    out["reviews"] = filtered_reviews
    return out


def _summary_transition_key(kind: str, block: Mapping[str, Any]) -> str:
    if kind == "head_commit":
        return f"head_commit:{block.get('previous_sha', '')}:{block.get('sha', '')}"
    head = str(block.get("head_sha") or "")
    return f"{kind}:{head}:{block.get('from', '')}:{block.get('to', '')}"


def filter_wake_summary_by_event_memory(
    summary: Mapping[str, Any],
    ledger: EventLedger,
) -> dict[str, Any]:
    """Remove summary transitions already recorded in the event ledger."""
    out = dict(summary)
    for kind in ("ci_transition", "merge_state_change", "head_commit"):
        block = summary.get(kind)
        if not isinstance(block, dict):
            continue
        key = _summary_transition_key(kind, block)
        if key in ledger.reported:
            out[kind] = None
    overlap = summary.get("base_file_overlap")
    if isinstance(overlap, dict):
        key = str(overlap.get("event_key") or "")
        if key and key in ledger.reported:
            out["base_file_overlap"] = None
    return out


def mark_wake_summary_reported(
    ledger: EventLedger,
    summary: Mapping[str, Any],
    *,
    now: datetime | None = None,
) -> None:
    """Record non-comment wake-summary events as reported."""
    now = now or _utc_now()
    stamp = _iso_z(now)
    for kind in ("ci_transition", "merge_state_change"):
        block = summary.get(kind)
        if isinstance(block, dict):
            ledger.reported[_summary_transition_key(kind, block)] = stamp
    head = summary.get("head_commit")
    if isinstance(head, dict):
        ledger.reported[_summary_transition_key("head_commit", head)] = stamp
    overlap = summary.get("base_file_overlap")
    if isinstance(overlap, dict):
        key = str(overlap.get("event_key") or "")
        if key:
            ledger.reported[key] = stamp


def mark_delta_reported(
    ledger: EventLedger,
    delta: Mapping[str, Any],
    *,
    now: datetime | None = None,
) -> None:
    """Record REST delta comment/review events as reported."""
    now = now or _utc_now()
    stamp = _iso_z(now)
    for item in delta.get("issue_comments") or []:
        if isinstance(item, dict):
            ledger.reported[_event_key_issue_comment(item)] = stamp
    for item in delta.get("review_comments") or []:
        if isinstance(item, dict):
            ledger.reported[_event_key_review_comment(item)] = stamp
    for item in delta.get("reviews") or []:
        if isinstance(item, dict):
            ledger.reported[_event_key_review(item)] = stamp


def _paged_json_list(http: HttpGet, path_prefix: str) -> list[dict[str, Any]]:
    owner_path = path_prefix
    items: list[dict[str, Any]] = []
    page = 1
    joiner = "&" if "?" in owner_path else "?"
    while True:
        body = _safe_json_get(http, f"{owner_path}{joiner}per_page=100&page={page}")
        if not isinstance(body, list) or not body:
            break
        items.extend(item for item in body if isinstance(item, dict))
        if len(body) < 100:
            break
        page += 1
    return items


def _filenames_from_compare(body: Mapping[str, Any] | None) -> set[str]:
    if not isinstance(body, dict):
        return set()
    names: set[str] = set()
    for item in body.get("files") or []:
        if isinstance(item, dict):
            name = item.get("filename")
            if name:
                names.add(str(name))
    return names


def detect_base_moved_into_pr_files(
    http: HttpGet,
    repo: str,
    pr_number: int,
    *,
    previous_base_sha: str | None,
    current_base_sha: str | None,
) -> list[str]:
    """Return PR file paths also touched by new base-branch commits (#1246 guard 3)."""
    if not previous_base_sha or not current_base_sha:
        return []
    if previous_base_sha == current_base_sha:
        return []
    owner, name = _split_repo(repo)
    compare = _safe_json_get(
        http,
        f"/repos/{owner}/{name}/compare/{previous_base_sha}...{current_base_sha}",
    )
    base_touched = _filenames_from_compare(compare if isinstance(compare, dict) else None)
    if not base_touched:
        return []
    pr_files = {
        str(item.get("filename"))
        for item in _paged_json_list(http, f"/repos/{owner}/{name}/pulls/{pr_number}/files")
        if item.get("filename")
    }
    overlap = sorted(path for path in pr_files if path in base_touched)
    return overlap


def base_file_overlap_summary(
    overlap_paths: list[str],
    *,
    previous_base_sha: str,
    current_base_sha: str,
) -> dict[str, Any] | None:
    if not overlap_paths:
        return None
    digest = hashlib.sha256("\n".join(overlap_paths).encode("utf-8")).hexdigest()[:12]
    event_key = f"base_overlap:{current_base_sha}:{digest}"
    return {
        "previous_base_sha": previous_base_sha,
        "current_base_sha": current_base_sha,
        "paths": overlap_paths,
        "event_key": event_key,
    }

