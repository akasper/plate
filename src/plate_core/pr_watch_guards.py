"""Watcher guards for ``gh plate pr babysit --watch`` (#1233).

Ideas adapted from t3dotgg/tstack ``pr-wait`` (MIT, Theo Browne); implementation
and wording are PLATE-original. Parent cost model: #1077 (ETag probes, backoff,
delta wakes — no tight polling loops).
"""

from __future__ import annotations

import fnmatch
import hashlib
import re
from typing import Any, Mapping, Protocol

from .github_client import GhApiError, GhClient

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

