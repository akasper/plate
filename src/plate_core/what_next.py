"""What-next recommendation for PLATE agents (#282 / #654 / #793 harden).

Priority (cheap → specific):
1. Critical/exhausted durable budget pressure (surface gates still apply under risk=off)
2. Open PRs targeting integration base (babysit to green)
3. Missing labels → bootstrap
4. Missing multi-track release standing branches → release repair (#320/#814)
5. Actionable local SPEC audit findings (#340 health/drift)
6. Concrete ready Feature/Bug candidates (status:ready-to-work or implementable)
7. Project Manager orchestrator (#660): checkpoints → tick delegated → proposed → active queue only
8. Open Epics with idle PM → first-slice closeout / stub refine (not PM dry-run solely from open_epic_count; #905)
   — when available, name concrete complete-child Epic candidates (#909)
9. Pending fragments / release status
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote_plus


def _missing_release_tracks(release_status: dict[str, Any]) -> list[str]:
    """Return missing multi-track standing branch names from get_release_status shape."""
    tracks = release_status.get("release_track_branches") or {}
    if not isinstance(tracks, dict):
        tracks = {}
    missing: list[str] = []
    for name in ("release-major", "release-minor", "release-patch"):
        # Explicit false, or absent while mode is legacy / needs repair
        present = tracks.get(name)
        if present is False or (
            present is None
            and str(release_status.get("release_branch_mode") or "") == "legacy"
        ):
            missing.append(name)
    # Also honor repair diagnosis when attached
    diag = release_status.get("diagnosis") or {}
    if isinstance(diag, dict):
        for name in diag.get("missing_branches") or []:
            n = str(name)
            if n.startswith("release-") and n not in missing and n != "release":
                missing.append(n)
    return missing


def recommend_what_next(
    *,
    health: dict[str, Any] | None = None,
    budget: dict[str, Any] | None = None,
    open_prs: list[dict[str, Any]] | None = None,
    agent_type: str | None = None,
    pending_fragment_count: int | None = None,
    ready_issues: list[dict[str, Any]] | None = None,
    pm_status: dict[str, Any] | None = None,
    release_status: dict[str, Any] | None = None,
    epic_closeout_candidates: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Pure recommendation from pre-fetched state (testable).

    ``health``: get_health().to_dict() shape (label_coverage_ok, open_epic_count, budget_*).
    ``budget``: get_budget_snapshot() or cost dashboard budget dict.
    ``open_prs``: list of {number, title, baseRefName, mergeable?} for open PRs.
    ``ready_issues``: list of {number, title, labels?} implementable Feature/Bug candidates.
    ``pm_status``: get_pm_status().to_dict() shape for #660 orchestrator ranking.
    ``release_status``: get_release_status() shape for multi-track standing repair (#814).
    ``epic_closeout_candidates``: open Epics with all children closed (#909).
    """
    h = dict(health or {})
    b = dict(budget or {})
    prs = list(open_prs or [])
    ready = list(ready_issues or [])
    pm = dict(pm_status or {})
    rel = dict(release_status or {})
    closeouts = list(epic_closeout_candidates or [])
    labels_ok = bool(h.get("label_coverage_ok", False))
    open_epics = int(h.get("open_epic_count") or 0)
    missing_tracks = _missing_release_tracks(rel) if rel else []
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
    # Next-cycle pause from snapshot/dashboard (may be true while pressure is only elevated)
    def _truthy(v: object) -> bool:
        if isinstance(v, bool):
            return v
        if v is None:
            return False
        return str(v).lower() in ("1", "true", "yes")

    would_pause_next = _truthy(
        b.get("would_pause_next_cycle")
        if b.get("would_pause_next_cycle") is not None
        else b.get("would_pause")
    ) or _truthy(
        h.get("budget_would_pause_next_cycle")
        if h.get("budget_would_pause_next_cycle") is not None
        else h.get("would_pause_next_cycle")
    )

    quiet = (
        " For any looped execution, use terse one-sentence bullet turn summaries and "
        "post comments only on meaningful progress (quiet_operations guidance)."
    )

    sa_status = str(h.get("spec_audit_status") or "").lower() or None
    sa_actionable = h.get("spec_audit_actionable_count")
    try:
        sa_actionable_n = int(sa_actionable) if sa_actionable is not None else 0
    except (TypeError, ValueError):
        sa_actionable_n = 0
    sa_next = h.get("spec_audit_next_step")

    def _pm_int(key: str) -> int:
        try:
            return int(pm.get(key) or 0)
        except (TypeError, ValueError):
            return 0

    pm_checkpoints = _pm_int("open_checkpoints")
    pm_delegated = _pm_int("delegated")
    pm_proposed = _pm_int("proposed")
    pm_queue = _pm_int("queue_size")
    pm_open = _pm_int("open_assignments")
    pm_pressure = str(pm.get("budget_pressure") or "ok").lower()
    pm_risk = str(pm.get("risk_tolerance") or risk or "off")

    state = {
        "label_coverage_ok": labels_ok,
        "open_epic_count": open_epics,
        "budget_pressure": pressure,
        "budget_remaining_tokens": rem,
        "budget_daily_limit": daily,
        "budget_risk_tolerance": risk,
        "would_pause_next_cycle": would_pause_next,
        "open_pr_count": len(prs),
        "pending_fragment_count": pending_fragment_count,
        "ready_issue_count": len(ready),
        "spec_audit_status": sa_status,
        "spec_audit_actionable_count": sa_actionable_n,
        "pm_open_checkpoints": pm_checkpoints,
        "pm_delegated": pm_delegated,
        "pm_proposed": pm_proposed,
        "pm_queue_size": pm_queue,
        "pm_open_assignments": pm_open,
        "pm_budget_pressure": pm_pressure,
        "pm_risk_tolerance": pm_risk,
        "release_branch_mode": rel.get("release_branch_mode"),
        "missing_release_tracks": missing_tracks,
        "epic_closeout_candidate_count": len(closeouts),
    }

    # 1) Budget critical/exhausted OR next-cycle pause — even under risk=off (surface gates).
    # would_pause_next_cycle can be true while pressure is only elevated (remaining < per_cycle).
    if (
        pressure in ("critical", "exhausted")
        or would_pause_next
        or (rem is not None and daily is not None and int(rem) <= 0)
    ):
        action = (
            "resolve durable budget pressure before starting large work "
            f"(pressure={pressure}, remaining={rem}/{daily}"
            f"{', would_pause_next_cycle' if would_pause_next else ''})"
        )
        prompt = (
            "Budget gate is critical/exhausted or next-cycle pause is projected. "
            "Present ask_user_question from plate_costs dashboard=true / feed "
            "budget_gate options (raise .plate token_budget, wait for UTC day reset, "
            "or pause large starts). Do not open large Feature/Bug loops or planning "
            "builds until remaining recovers. risk_tolerance=off only disables "
            "AutonomyEngine cycles — surface live gates still apply."
            + quiet
        )
        return {
            "next_action": action,
            "prompt_segment": prompt,
            "rationale": (
                "budget_pressure critical/exhausted or would_pause_next_cycle "
                "(#634/#653/#787)"
            ),
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

    # 4) Multi-track standing release repair (#320 / #814)
    if missing_tracks:
        names = ", ".join(missing_tracks)
        return {
            "next_action": (
                f"repair missing release track branches ({names}) "
                "via gh plate release repair"
            ),
            "prompt_segment": (
                "Release standing state is drifted/legacy: multi-track branches "
                f"missing ({names}). Run `gh plate release status`, then "
                "`gh plate release repair` (dry-run) and `--apply` when safe "
                "(or MCP plate_release_repair). Creates release-major/minor/patch "
                "from default branch without duplicating Next Release. Do not start "
                "new Feature work on wrong base while tracks are missing."
                + quiet
            ),
            "rationale": f"missing release tracks: {names} (#320/#814)",
            "state_snapshot": state,
            "agent_type": agent_type or "general",
            "priority": "release_repair",
            "missing_release_tracks": missing_tracks,
        }

    # 5) Actionable SPEC audit findings from health (#340)
    if sa_status == "actionable" or sa_actionable_n > 0:
        step = str(sa_next or "").strip() or (
            "Run gh plate spec-audit --json then plan follow-ups "
            "(gh plate spec-audit --followups); never auto-write SPEC.md"
        )
        action = (
            f"resolve actionable SPEC audit findings "
            f"(actionable={sa_actionable_n}, status={sa_status or 'actionable'})"
        )
        prompt = (
            "Health reports actionable SPEC drift (#340). "
            f"Next: {step}. Prefer plate_spec_audit / plate_spec_audit_followups "
            "or Documentation PRs that add implemented+tested behavior to SPEC. "
            "Human-approval gate for SPEC.md writes."
            + quiet
        )
        return {
            "next_action": action,
            "prompt_segment": prompt,
            "rationale": "spec_audit_status actionable via plate_health (#340)",
            "state_snapshot": state,
            "agent_type": agent_type or "general",
            "priority": "spec_audit",
        }

    # 4b) Advisory-only SPEC audit — surface before generic epic when no ready work
    if sa_status == "advisory" and not ready:
        step = str(sa_next or "").strip() or "Review SPEC with gh plate spec-audit"
        return {
            "next_action": f"review advisory SPEC audit: {step[:120]}",
            "prompt_segment": (
                "Health reports advisory-only SPEC audit status. "
                f"{step} Then continue with ready Features or open Epics."
                + quiet
            ),
            "rationale": "spec_audit_status advisory (#340)",
            "state_snapshot": state,
            "agent_type": agent_type or "general",
            "priority": "spec_audit_advisory",
        }

    # 5) Concrete ready Feature/Bug — prefer over generic epic text (#793)
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

    # 6) Project Manager orchestrator (#660) — empty pipeline prefers PM over generic epic
    if pm_checkpoints > 0:
        return {
            "next_action": (
                f"resolve {pm_checkpoints} open PM/human checkpoint(s) before new assignments"
            ),
            "prompt_segment": (
                "PM is paused on open checkpoints (#648/#660). Run plate_pm_status / "
                "gh plate pm --status, list open checkpoints, and only proceed after "
                "human approval or checkpoint resolution. Do not plate_pm_run_cycle "
                "--apply while checkpoints remain."
                + quiet
            ),
            "rationale": "pm_status.open_checkpoints > 0 (#660)",
            "state_snapshot": state,
            "agent_type": agent_type or "general",
            "priority": "pm_checkpoint",
        }

    if pm_delegated > 0:
        return {
            "next_action": (
                f"tick {pm_delegated} delegated PM loop assignment(s) "
                f"(plate_pm_tick_loops / gh plate pm --tick-loops)"
            ),
            "prompt_segment": (
                "PM queue has delegated feature/bug loops (#660). Run "
                "`gh plate pm --tick-loops` or plate_pm_tick_loops (dry_run first), "
                "babysit any open PRs those loops surface, then plate_pm_complete when "
                "done. risk_tolerance=off still allows tick/status; avoid unsupervised "
                "AutonomyEngine --loop."
                + quiet
            ),
            "rationale": f"pm delegated={pm_delegated} (#660)",
            "state_snapshot": state,
            "agent_type": agent_type or "general",
            "priority": "pm_tick",
        }

    # Proposed rows first: explicit Approve & run before opening more assigns (#891/#892)
    if pm_proposed > 0:
        return {
            "next_action": (
                f"approve & run {pm_proposed} proposed PM assignment(s) "
                f"(plate_pm_complete status=run / feed Approve & run)"
            ),
            "prompt_segment": (
                "PM queue has proposed assignments awaiting explicit consent (#660/#892). "
                "1) plate_pm_queue / gh plate pm --queue --status proposed  "
                "2) Present feed/TUI Approve & run  "
                "3) plate_pm_complete <assignment_id> status=run "
                "(or gh plate pm --complete ID --complete-status run) to promote→delegated "
                "with fleet/loop dispatch — works under risk=off  "
                "4) implement/tick the delegated packet, then plate_pm_complete status=done. "
                "Do not open more PM assigns until proposed rows are run, deferred, or cancelled. "
                "Do not start browser #661."
                + quiet
            ),
            "rationale": f"pm proposed={pm_proposed} need explicit approve&run (#660/#892)",
            "state_snapshot": state,
            "agent_type": agent_type or "general",
            "priority": "pm_propose_run",
        }

    # Active PM work only — do not force PM dry-run solely because open_epic_count > 0
    # (#905). First-slice Epics stay open under #654, so open_epics is almost always high.
    if pm_queue > 0 or pm_open > 0:
        action = (
            "run Project Manager cycle dry-run then assign/tick "
            f"(epics={open_epics}, queue={pm_queue}, proposed={pm_proposed})"
        )
        prompt = (
            "Pipeline empty with active PM queue — prefer the #660 orchestrator. "
            "1) gh plate release status  2) plate_pm_status / gh plate pm --status  "
            "3) plate_pm_run_cycle dry_run=true (or gh plate pm --run) to propose "
            "persona assignments from what_next+feed  4) with human judgment, "
            "Approve & run via plate_pm_complete status=run (works under risk=off); "
            "do not rely on autopilot when risk_tolerance=off. "
            "Use plate_pm_tick_loops for delegated loops. Do not start browser #661."
            + quiet
        )
        return {
            "next_action": action,
            "prompt_segment": prompt,
            "rationale": (
                f"empty pipeline → PM orchestrator (#660); "
                f"open_epics={open_epics} queue={pm_queue} pressure={pm_pressure}"
            ),
            "state_snapshot": state,
            "agent_type": agent_type or "general",
            "priority": "pm",
        }

    # 7) Open Epics, PM idle, no ready issues — closeouts / stub refine (#905/#909)
    if open_epics > 0:
        cand_bits: list[str] = []
        structured: list[dict[str, Any]] = []
        for c in closeouts[:8]:
            num = c.get("number") or c.get("epic_issue_number")
            title = str(c.get("title") or c.get("epic_issue_title") or "")[:60]
            if num is None:
                continue
            cand_bits.append(f"#{num}")
            structured.append(
                {
                    "number": int(num),
                    "title": title,
                    "children_total": c.get("children_total"),
                    "children_completed": c.get("children_completed"),
                }
            )
        if cand_bits:
            action = (
                "first-slice closeout for complete-child Epics "
                f"{', '.join(cand_bits)} (wiki + status:implemented); residual E2E under #654"
            )
            prompt = (
                "Pipeline empty, PM idle. Named Epics have all sub-issues closed (#909). "
                "For each: extend docs/wiki/V1-Autonomy-Surfaces-Epic-Closeouts.md (or "
                "epic wiki), add status:implemented if missing, post a summary comment. "
                "Do not claim full v1.0 / re-check #654 without E2E proof. Do not run "
                "plate_pm_run_cycle solely for open_epic_count. If closeouts already "
                "recorded, refine a need:refinement stub into status:ready-to-work."
                + quiet
            )
            rationale = (
                f"{len(structured)} complete-child Epic closeout candidate(s); "
                f"open_epics={open_epics} (#909/#905)"
            )
        else:
            action = (
                "advance open Epics: first-slice closeout for Epics with all children "
                "closed (wiki + status:implemented); else refine a need:refinement "
                "stub into status:ready-to-work and implement"
            )
            prompt = (
                "Pipeline empty, PM queue idle, no ready Features/Bugs. Do not run "
                "plate_pm_run_cycle just because open_epic_count > 0 (#905). "
                "1) gh plate release status  2) For Epics whose children are all closed "
                "(e.g. #656/#657/#658/#470 first slices), document outcomes in "
                "docs/wiki/ (extend V1-Autonomy-Surfaces-Epic-Closeouts.md), add "
                "status:implemented, post a summary comment — residual E2E stays under "
                "#654. 3) Otherwise refine a need:refinement/status:stub Feature into "
                "ACs + status:ready-to-work and implement the smallest slice with tests + "
                "fragment + PR to release. Prefer v1.0 path over marketplace human Tasks."
                + quiet
            )
            rationale = (
                f"{open_epics} open Epic(s); PM idle (queue=0) — closeout or refine (#905)"
            )
        out: dict[str, Any] = {
            "next_action": action,
            "prompt_segment": prompt,
            "rationale": rationale,
            "state_snapshot": state,
            "agent_type": agent_type or "general",
            "priority": "epic",
        }
        if structured:
            out["epic_closeout_candidates"] = structured
        return out

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


def fetch_epic_closeout_candidates(
    repo: str | None = None,
    *,
    limit: int = 8,
    gh: Any | None = None,
) -> list[dict[str, Any]]:
    """Open Epic issues whose sub-issues are all closed (first-slice closeout candidates).

    Uses GraphQL ``subIssuesSummary`` when available. Degrades to [] on failure (#909).
    Only returns Epics with ``total > 0`` and ``completed == total`` (skips empty stubs).
    Skips Epics already labeled ``status:implemented`` (first-slice recorded; #913).
    """
    from .github_client import GhClient
    from .health import resolve_repo

    target = resolve_repo(repo)
    owner, _, name = target.partition("/")
    if not owner or not name:
        return []
    client = gh or GhClient()
    query = """
    query($owner: String!, $name: String!) {
      repository(owner: $owner, name: $name) {
        issues(
          first: 25
          states: OPEN
          labels: ["Epic"]
          orderBy: {field: UPDATED_AT, direction: DESC}
        ) {
          nodes {
            number
            title
            labels(first: 20) {
              nodes {
                name
              }
            }
            subIssuesSummary {
              total
              completed
            }
          }
        }
      }
    }
    """
    try:
        data = client.api(
            "graphql",
            method="POST",
            fields={"query": query, "owner": owner, "name": name},
        )
    except Exception:
        return []
    if not isinstance(data, dict):
        return []
    nodes = (
        ((data.get("data") or {}).get("repository") or {}).get("issues") or {}
    ).get("nodes") or []
    out: list[dict[str, Any]] = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        lab_nodes = ((node.get("labels") or {}).get("nodes")) or []
        lab_names = {
            str(x.get("name") or "")
            for x in lab_nodes
            if isinstance(x, dict)
        }
        # First-slice already recorded — do not re-queue every idle cycle (#913)
        if "status:implemented" in lab_names:
            continue
        summary = node.get("subIssuesSummary") or {}
        try:
            total = int(summary.get("total") or 0)
            completed = int(summary.get("completed") or 0)
        except (TypeError, ValueError):
            continue
        if total <= 0 or completed != total:
            continue
        num = node.get("number")
        if num is None:
            continue
        out.append(
            {
                "number": int(num),
                "title": str(node.get("title") or "")[:120],
                "children_total": total,
                "children_completed": completed,
            }
        )
        if len(out) >= limit:
            break
    return out


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

    # 2) Fallback: open Feature / Bug / Documentation without refinement/stub/implemented.
    # Run separate label queries — GitHub search often returns 0 hits for parenthesized
    # OR groups of label: qualifiers, which starved ready candidates (#654/#660).
    if len(out) < limit:
        exclude = (
            "-label:status:implemented -label:status:stub "
            "-label:need:refinement -label:need:human-review -label:status:blocked"
        )
        for type_label in ("Feature", "Bug", "Documentation"):
            if len(out) >= limit:
                break
            try:
                q2 = (
                    f"repo:{target} is:issue is:open "
                    f"label:{type_label} {exclude}"
                )
                data = (
                    client.api(
                        f"search/issues?q={quote_plus(q2)}&per_page={min(limit * 2, 30)}"
                    )
                    or {}
                )
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
    include_pm: bool = True,
    include_release: bool = True,
) -> dict[str, Any]:
    """Live what-next: health + budget + PRs + ready issues + PM + release standing."""
    health: dict[str, Any] = {}
    budget: dict[str, Any] = {}
    open_prs: list[dict[str, Any]] = []
    ready_issues: list[dict[str, Any]] = []
    pending_fragment_count: int | None = None
    pm_status: dict[str, Any] | None = None
    release_status: dict[str, Any] | None = None

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

    if include_release and not open_prs:
        try:
            from .release import get_release_status

            rs = get_release_status(repo=repo)
            release_status = rs.to_dict() if hasattr(rs, "to_dict") else dict(rs or {})
        except Exception:
            release_status = None

    if include_pm and not open_prs and not ready_issues:
        # Local PM queue/status only when pipeline is empty (avoid work when PRs win).
        try:
            from .pm import get_pm_status

            # repo=None keeps status offline-safe (queue + .plate); live autonomy optional.
            pm_status = get_pm_status(None)
        except Exception:
            pm_status = None

    epic_closeout_candidates: list[dict[str, Any]] = []
    # Only when pipeline empty and PM idle — avoid GraphQL when PRs/ready/PM win ranking.
    pm_active = False
    if isinstance(pm_status, dict):
        try:
            pm_active = (
                int(pm_status.get("queue_size") or 0) > 0
                or int(pm_status.get("open_assignments") or 0) > 0
                or int(pm_status.get("open_checkpoints") or 0) > 0
                or int(pm_status.get("delegated") or 0) > 0
                or int(pm_status.get("proposed") or 0) > 0
            )
        except (TypeError, ValueError):
            pm_active = False
    if not open_prs and not ready_issues and not pm_active:
        try:
            epic_closeout_candidates = fetch_epic_closeout_candidates(repo, limit=8)
        except Exception:
            epic_closeout_candidates = []

    return recommend_what_next(
        health=health,
        budget=budget,
        open_prs=open_prs,
        agent_type=agent_type,
        pending_fragment_count=pending_fragment_count,
        ready_issues=ready_issues,
        pm_status=pm_status,
        release_status=release_status,
        epic_closeout_candidates=epic_closeout_candidates,
    )
