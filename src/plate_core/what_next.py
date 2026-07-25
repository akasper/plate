"""What-next recommendation for PLATE agents (#282 / #654 / #793 harden).

Priority (cheap → specific):
1. Critical/exhausted durable budget pressure (surface gates still apply under risk=off)
2. Open PRs targeting integration base (babysit to green)
3. Missing labels → bootstrap
4. Concrete ready Feature/Bug candidates (status:ready-to-work or implementable)
5. Open Epics → advance ready child Feature/Bug (generic when no candidates)
6. Pending fragments / release status
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote_plus


def recommend_what_next(
    *,
    health: dict[str, Any] | None = None,
    budget: dict[str, Any] | None = None,
    open_prs: list[dict[str, Any]] | None = None,
    agent_type: str | None = None,
    pending_fragment_count: int | None = None,
    ready_issues: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Pure recommendation from pre-fetched state (testable).

    ``health``: get_health().to_dict() shape (label_coverage_ok, open_epic_count, budget_*).
    ``budget``: get_budget_snapshot() or cost dashboard budget dict.
    ``open_prs``: list of {number, title, baseRefName, mergeable?} for open PRs.
    ``ready_issues``: list of {number, title, labels?} implementable Feature/Bug candidates.
    """
    h = dict(health or {})
    b = dict(budget or {})
    prs = list(open_prs or [])
    ready = list(ready_issues or [])
    labels_ok = bool(h.get("label_coverage_ok", False))
    open_epics = int(h.get("open_epic_count") or 0)
    pressure = str(
        b.get("budget_pressure")
        or h.get("budget_pressure")
        or "ok"
    ).lower()
    rem = b.get("remaining_tokens")
    if rem is None:
        rem = h.get("budget_remaining_tokens")
    daily = b.get("daily_limit") or h.get("budget_daily_limit")
    risk = str(b.get("risk_tolerance") or h.get("budget_risk_tolerance") or "off")

    quiet = (
        " For any looped execution, use terse one-sentence bullet turn summaries and "
        "post comments only on meaningful progress (quiet_operations guidance)."
    )

    state = {
        "label_coverage_ok": labels_ok,
        "open_epic_count": open_epics,
        "budget_pressure": pressure,
        "budget_remaining_tokens": rem,
        "budget_daily_limit": daily,
        "budget_risk_tolerance": risk,
        "open_pr_count": len(prs),
        "pending_fragment_count": pending_fragment_count,
        "ready_issue_count": len(ready),
    }

    # 1) Budget critical/exhausted — even under risk=off (surface gates)
    if pressure in ("critical", "exhausted") or (
        rem is not None and daily is not None and int(rem) <= 0
    ):
        action = (
            "resolve durable budget pressure before starting large work "
            f"(pressure={pressure}, remaining={rem}/{daily})"
        )
        prompt = (
            "Budget gate is critical/exhausted. Present ask_user_question from "
            "plate_costs dashboard=true / feed budget_gate options (raise .plate "
            "token_budget, wait for UTC day reset, or pause large starts). "
            "Do not open large Feature/Bug loops or planning builds until remaining "
            "recovers. risk_tolerance=off only disables AutonomyEngine cycles — "
            "surface live gates still apply."
            + quiet
        )
        return {
            "next_action": action,
            "prompt_segment": prompt,
            "rationale": "budget_pressure critical/exhausted (#634/#653/#787)",
            "state_snapshot": state,
            "agent_type": agent_type or "general",
            "priority": "budget_gate",
        }

    # 2) Open PRs on release/integration → babysit first
    release_prs = [
        p
        for p in prs
        if str(p.get("baseRefName") or p.get("base") or "")
        in ("release", "release-major", "release-minor", "release-patch")
        or str(p.get("baseRefName") or "").startswith("release")
    ]
    candidates = release_prs or prs
    if candidates:
        first = candidates[0]
        num = first.get("number") or first.get("pr_number")
        title = str(first.get("title") or "")[:80]
        action = f"babysit open PR #{num} to CLEAN then human merge: {title}"
        prompt = (
            f"Prefer finishing open agent PRs over new work. Run "
            f"`gh plate release status` then `gh plate pr babysit {num} --act` "
            f"(scope all). CI diagnosis first if red. Resolve threads; do not "
            f"self-merge when risk_tolerance=off — leave for human merge when CLEAN."
            + quiet
        )
        return {
            "next_action": action,
            "prompt_segment": prompt,
            "rationale": f"{len(candidates)} open PR(s); finish pipeline before new work",
            "state_snapshot": state,
            "agent_type": agent_type or "general",
            "priority": "open_pr",
            "pr_number": num,
        }

    # 3) Labels / bootstrap
    if not labels_ok:
        action = "run bootstrap to establish labels/wiki/epic/starters"
        prompt = (
            "Follow the PLATE bootstrap flow: create required labels, enable wiki, "
            "seed initial Epic, seed starter Questions from catalog. Then create a "
            "Goals wiki page per convention and use it for audits."
            + quiet
        )
        return {
            "next_action": action,
            "prompt_segment": prompt,
            "rationale": "label_coverage_ok false",
            "state_snapshot": state,
            "agent_type": agent_type or "general",
            "priority": "bootstrap",
        }

    # 4) Concrete ready Feature/Bug — prefer over generic epic text (#793)
    if ready:
        first = ready[0]
        num = first.get("number") or first.get("issue_number")
        title = str(first.get("title") or "")[:80]
        action = f"implement ready issue #{num}: {title}"
        prompt = (
            f"Pipeline empty; start highest ready candidate #{num}. "
            f"Run `gh plate release status` first, branch from origin/release as "
            f"feature/{num}-short-slug (or bug/). TDD when code; author fragment "
            f"under .agentic/releases/unreleased/; open PR targeting release with "
            f"Closes #{num} in the body only; then babysit that PR to CLEAN. "
            f"Prefer v1.0 path (#654): safety → feed → PM over marketplace Tasks."
            + quiet
        )
        return {
            "next_action": action,
            "prompt_segment": prompt,
            "rationale": f"{len(ready)} ready/implementable issue candidate(s) (#793)",
            "state_snapshot": state,
            "agent_type": agent_type or "general",
            "priority": "ready_issue",
            "issue_number": num,
            "issue_title": title,
            "ready_issues": [
                {
                    "number": i.get("number") or i.get("issue_number"),
                    "title": str(i.get("title") or "")[:120],
                }
                for i in ready[:10]
            ],
        }

    # 5) Open Epics → advance ready child (generic when no candidates listed)
    if open_epics > 0:
        action = (
            "advance an open Epic: pick a child Feature/Bug with tests sketched, "
            "no need:refinement"
        )
        prompt = (
            "Use plate_epic_status or gh plate epic status to list children. For a "
            "Feature: read full issue, add/update tests first, implement smallest "
            "change, author fragment in .agentic/releases/unreleased/, PR with clean "
            "title + labels (Feature + area) + Closes #N in body only, babysit with "
            "gh plate pr babysit. Prefer v1.0 path (#654): safety → feed → PM."
            + quiet
        )
        return {
            "next_action": action,
            "prompt_segment": prompt,
            "rationale": f"{open_epics} open Epic(s)",
            "state_snapshot": state,
            "agent_type": agent_type or "general",
            "priority": "epic",
        }

    # 6) Fragments / release
    if pending_fragment_count is not None and int(pending_fragment_count) > 0:
        action = (
            f"review {pending_fragment_count} pending unreleased fragments; "
            "prepare release cut when ready"
        )
        prompt = (
            "Run gh plate release status. Review unreleased fragments; do not cut "
            "v1.0.0 without #654 checklist E2E proof. Continue Phase work or "
            "stabilize release branch."
            + quiet
        )
        return {
            "next_action": action,
            "prompt_segment": prompt,
            "rationale": "pending unreleased fragments",
            "state_snapshot": state,
            "agent_type": agent_type or "general",
            "priority": "fragments",
        }

    action = "check for pending release fragments or next beta/v1.0 item"
    prompt = (
        "Run gh plate release status. If unreleased fragments, prepare for cut_release "
        "when ceremony-ready. Otherwise pick highest unfinished #654 residual "
        "(Phase 2 feed/planning or Phase 3 PM) — not sketches or marketplace human Tasks."
        + quiet
    )
    return {
        "next_action": action,
        "prompt_segment": prompt,
        "rationale": "default fallback after health/budget/PR checks",
        "state_snapshot": state,
        "agent_type": agent_type or "general",
        "priority": "default",
    }


def _issue_label_names(item: dict[str, Any]) -> list[str]:
    raw = item.get("labels") or []
    names: list[str] = []
    for lab in raw:
        if isinstance(lab, dict):
            n = lab.get("name")
            if n:
                names.append(str(n))
        elif lab:
            names.append(str(lab))
    return names


def _normalize_ready_issue(item: dict[str, Any]) -> dict[str, Any] | None:
    num = item.get("number")
    if num is None:
        return None
    return {
        "number": int(num),
        "title": str(item.get("title") or ""),
        "labels": _issue_label_names(item),
    }


def fetch_ready_issue_candidates(
    repo: str | None = None,
    *,
    limit: int = 10,
    gh: Any | None = None,
) -> list[dict[str, Any]]:
    """Fetch open implementable Feature/Bug candidates for empty-pipeline what_next.

    Prefer ``status:ready-to-work``. Fall back to Feature/Bug without
    ``need:refinement``, ``status:stub``, or ``status:implemented``.
    Skip Epic/Release/Task types and human-only blockers.
    """
    from .github_client import GhClient
    from .health import resolve_repo

    target = resolve_repo(repo)
    client = gh or GhClient()
    seen: set[int] = set()
    out: list[dict[str, Any]] = []

    def _absorb(items: list[Any], *, require_ready_label: bool) -> None:
        for item in items:
            if not isinstance(item, dict) or len(out) >= limit:
                return
            norm = _normalize_ready_issue(item)
            if not norm:
                continue
            n = int(norm["number"])
            if n in seen:
                continue
            labs = {x.lower() for x in norm["labels"]}
            if require_ready_label and "status:ready-to-work" not in labs:
                continue
            # Skip non-work issue types and already-landed / blocked work
            if labs & {
                "epic",
                "release",
                "task",
                "status:implemented",
                "status:stub",
                "need:refinement",
                "need:human-review",
                "status:blocked",
            }:
                continue
            # Prefer Feature/Bug; allow bare status:ready-to-work without type
            type_ok = bool(labs & {"feature", "bug", "documentation", "feedback response"})
            if not require_ready_label and not type_ok:
                continue
            if require_ready_label and not type_ok and "status:ready-to-work" not in labs:
                continue
            seen.add(n)
            out.append(norm)

    # 1) Explicit ready-to-work
    try:
        q1 = f"repo:{target} is:issue is:open label:status:ready-to-work"
        data = client.api(f"search/issues?q={quote_plus(q1)}&per_page={min(limit, 20)}") or {}
        items = data.get("items") if isinstance(data, dict) else None
        if isinstance(items, list):
            _absorb(items, require_ready_label=True)
    except Exception:
        pass

    # 2) Fallback: open Feature/Bug without refinement/stub/implemented
    if len(out) < limit:
        try:
            q2 = (
                f"repo:{target} is:issue is:open "
                f"(label:Feature OR label:Bug) "
                f"-label:status:implemented -label:status:stub "
                f"-label:need:refinement -label:need:human-review -label:status:blocked"
            )
            data = client.api(f"search/issues?q={quote_plus(q2)}&per_page={min(limit * 2, 30)}") or {}
            items = data.get("items") if isinstance(data, dict) else None
            if isinstance(items, list):
                _absorb(items, require_ready_label=False)
        except Exception:
            pass

    return out[:limit]


def get_what_next(
    repo: str | None = None,
    agent_type: str | None = None,
    *,
    include_prs: bool = True,
    include_budget: bool = True,
    include_fragments: bool = True,
    include_ready_issues: bool = True,
) -> dict[str, Any]:
    """Live what-next: health + budget snapshot + optional open PRs + ready issues."""
    health: dict[str, Any] = {}
    budget: dict[str, Any] = {}
    open_prs: list[dict[str, Any]] = []
    ready_issues: list[dict[str, Any]] = []
    pending_fragment_count: int | None = None

    try:
        from .health import get_health

        health = get_health(repo).to_dict()
    except Exception as exc:
        return {
            "next_action": "inspect with plate_health + plate_epic_status",
            "error": str(exc),
            "agent_type": agent_type or "general",
        }

    if include_budget:
        try:
            from .autonomy import get_budget_snapshot

            budget = get_budget_snapshot()
            # Prefer health budget_* if snapshot missing pressure
            if not budget.get("budget_pressure") and health.get("budget_pressure"):
                budget = {
                    **budget,
                    "budget_pressure": health.get("budget_pressure"),
                    "remaining_tokens": health.get("budget_remaining_tokens"),
                    "daily_limit": health.get("budget_daily_limit"),
                    "risk_tolerance": health.get("budget_risk_tolerance"),
                }
        except Exception:
            budget = {
                "budget_pressure": health.get("budget_pressure"),
                "remaining_tokens": health.get("budget_remaining_tokens"),
                "daily_limit": health.get("budget_daily_limit"),
                "risk_tolerance": health.get("budget_risk_tolerance"),
            }

    if include_prs:
        try:
            from .github_client import GhClient
            from .health import resolve_repo

            target = resolve_repo(repo)
            gh = GhClient()
            # Prefer open PRs against release* bases
            data = gh.api(f"repos/{target}/pulls?state=open&per_page=20")
            if isinstance(data, list):
                for pr in data:
                    if not isinstance(pr, dict):
                        continue
                    base = (pr.get("base") or {}).get("ref") if isinstance(pr.get("base"), dict) else pr.get("base")
                    open_prs.append(
                        {
                            "number": pr.get("number"),
                            "title": pr.get("title"),
                            "baseRefName": base,
                            "mergeable": pr.get("mergeable"),
                            "draft": pr.get("draft"),
                        }
                    )
        except Exception:
            open_prs = []

    if include_ready_issues and not open_prs:
        # Only spend search budget when pipeline is empty (PRs still win ranking).
        try:
            ready_issues = fetch_ready_issue_candidates(repo, limit=10)
        except Exception:
            ready_issues = []

    if include_fragments:
        try:
            from pathlib import Path

            from .release import collect_fragments

            frags = collect_fragments(Path(".agentic/releases"))
            pending_fragment_count = len(frags or [])
        except Exception:
            pending_fragment_count = None

    return recommend_what_next(
        health=health,
        budget=budget,
        open_prs=open_prs,
        agent_type=agent_type,
        pending_fragment_count=pending_fragment_count,
        ready_issues=ready_issues,
    )
