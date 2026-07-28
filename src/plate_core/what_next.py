"""What-next recommendation for PLATE agents (#282 / #654 / #793 harden).

Priority (cheap → specific):
1. Critical/exhausted durable budget pressure (surface gates still apply under risk=off)
2. Open PRs targeting integration base (babysit to green)
3. Missing labels → bootstrap
4. Missing multi-track release standing branches → release repair (#320/#814)
5. Actionable local SPEC audit findings (#340 health/drift)
6. Local adoption not core_ready → gh plate adopt / import-payload (#937 / #633 / #935)
7. Active adoption session timer → continue under-30m path / complete-session (#957 / #955 / #633)
8. Core adoption ready but first Q&A not seeded → gh plate adopt --first-qa-plan (#949 / #633)
9. Self-migrate pin/payload drift → gh plate self-migrate --plan (#941 / #649 / #939)
10. Concrete ready Feature/Bug candidates (status:ready-to-work or implementable)
11. Active scheduled op runs (blocked/running/planned) (#933 / #659 / #641)
12. Project Manager orchestrator (#660): checkpoints → tick delegated → proposed → active queue only
13. Runnable scheduled ops dry-run plan when pipeline + PM idle (#933)
14. Open Epics with idle PM → first-slice closeout / stub refine (not PM dry-run solely from open_epic_count; #905)
   — when available, name concrete complete-child Epic candidates (#909)
15. Pending fragments / release status
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
    scheduled_ops: dict[str, Any] | None = None,
    adoption: dict[str, Any] | None = None,
    adoption_session: dict[str, Any] | None = None,
    self_migrate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Pure recommendation from pre-fetched state (testable).

    ``health``: get_health().to_dict() shape (label_coverage_ok, open_epic_count, budget_*).
    ``budget``: get_budget_snapshot() or cost dashboard budget dict.
    ``open_prs``: list of {number, title, baseRefName, mergeable?} for open PRs.
    ``ready_issues``: list of {number, title, labels?} implementable Feature/Bug candidates.
    ``pm_status``: get_pm_status().to_dict() shape for #660 orchestrator ranking.
    ``release_status``: get_release_status() shape for multi-track standing repair (#814).
    ``epic_closeout_candidates``: open Epics with all children closed (#909).
    ``scheduled_ops``: scheduled_ops_status-like summary + optional active_runs (#933).
    ``adoption``: assess_adoption_readiness() shape (#937/#935); ranks when core_ready is false.
    ``adoption_session``: adoption_session_status() shape (#957/#955); ranks when active.
    ``self_migrate``: plan or verify shape (#941/#939/#969); ranks when drift is true
    or when verify ``ready`` is false (post-migrate residual after pin aligned).
    """
    h = dict(health or {})
    b = dict(budget or {})
    prs = list(open_prs or [])
    ready = list(ready_issues or [])
    pm = dict(pm_status or {})
    rel = dict(release_status or {})
    closeouts = list(epic_closeout_candidates or [])
    sops = dict(scheduled_ops or {})
    adopt = dict(adoption or {})
    adopt_sess = dict(adoption_session or {})
    smig = dict(self_migrate or {})
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
        "scheduled_ops_active_count": len(list(sops.get("active_runs") or [])),
        "scheduled_ops_runnable_count": len(
            list(sops.get("runnable_at_tolerance") or sops.get("runnable") or [])
        ),
        "scheduled_ops_gated_count": len(list(sops.get("gated") or [])),
        "adoption_core_ready": adopt.get("core_ready") if adopt else None,
        "adoption_minutes_remaining": adopt.get("estimated_minutes_remaining")
        if adopt
        else None,
        "first_qa_seeded": (adopt.get("first_qa") or {}).get("seeded")
        if adopt
        else None,
        "adoption_session_active": adopt_sess.get("active") if adopt_sess else None,
        "adoption_session_elapsed": adopt_sess.get("elapsed_minutes")
        if adopt_sess
        else None,
        "self_migrate_drift": smig.get("drift") if smig else None,
        "self_migrate_target": smig.get("target_version") if smig else None,
        "self_migrate_ready": smig.get("ready") if smig and "ready" in smig else None,
    }

    active_sop_runs = list(sops.get("active_runs") or [])
    runnable_sops = list(sops.get("runnable_at_tolerance") or sops.get("runnable") or [])
    adoption_not_ready = bool(adopt) and adopt.get("core_ready") is False
    self_migrate_drift = bool(smig) and smig.get("drift") is True
    self_migrate_not_ready = bool(smig) and smig.get("ready") is False

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

    # 5) Active adoption session timer — continue under-30m path (#957/#955/#633)
    # Ranks ahead of ready Features / self-migrate while session is in progress.
    # Takes precedence over plain adoption_not_ready so elapsed timer context is visible.
    if adopt_sess.get("active") is True:
        first_qa_s = adopt.get("first_qa") if adopt else None
        seeded = (
            isinstance(first_qa_s, dict) and first_qa_s.get("seeded") is True
        ) or adopt_sess.get("first_qa_seeded") is True
        core_ok = (
            adopt.get("core_ready") is True or adopt_sess.get("core_ready") is True
        )
        elapsed = adopt_sess.get("elapsed_minutes")
        if not core_ok:
            next_cmd = str(adopt.get("next_command") or "gh plate adopt --json")
            phase = "finish readiness"
        elif not seeded:
            next_cmd = "gh plate adopt --first-qa-plan --json"
            phase = "seed first Q&A"
        else:
            next_cmd = "gh plate adopt --complete-session --json"
            phase = "complete session timer"
        elapsed_s = f" elapsed≈{elapsed}m" if elapsed is not None else ""
        return {
            "next_action": (
                f"continue adoption session ({phase}{elapsed_s}): {next_cmd}"
            ),
            "prompt_segment": (
                "Active adoption wall-clock session (#955/#957/#633). "
                f"Phase: {phase}. "
                "1) Follow next_command  "
                "2) `gh plate adopt --session-status --json` for elapsed/within_30m_so_far  "
                "3) When core_ready + first_qa seeded: "
                "`gh plate adopt --complete-session --json` to record proof. "
                "Do not start ready Features until session completes or is deferred."
                + quiet
            ),
            "rationale": (
                f"adoption_session active; phase={phase}; "
                f"elapsed_minutes={elapsed} (#957/#955/#633)"
            ),
            "state_snapshot": state,
            "agent_type": agent_type or "general",
            "priority": "adoption_session",
            "next_command": next_cmd,
            "elapsed_minutes": elapsed,
            "within_30m_so_far": adopt_sess.get("within_30m_so_far"),
            "ask_user_question": {
                "question": f"Adoption session active{elapsed_s} — continue under-30m path?",
                "options": [
                    {"label": "Follow next command", "description": next_cmd},
                    {
                        "label": "Session status",
                        "description": "gh plate adopt --session-status --json",
                    },
                    {
                        "label": "Complete session",
                        "description": "gh plate adopt --complete-session --json",
                    },
                ],
            },
        }

    # 5b) Local adoption incomplete — finish <30m path before new Features (#937/#633)
    if adoption_not_ready:
        mins = adopt.get("estimated_minutes_remaining")
        next_cmd = str(adopt.get("next_command") or "gh plate adopt --json")
        action = (
            f"complete local PLATE adoption (~{mins}m remaining): "
            f"{next_cmd}"
        )
        prompt = (
            "Local checkout fails core adoption readiness (#935/#633). "
            "1) `gh plate adopt --json` / plate_adoption_status  "
            "2) Follow next_command (usually import-payload dry-run then apply, "
            "then bootstrap --adopt)  "
            "3) Re-check adopt until core_ready; stay within 30m budget. "
            "Do not start ready Feature work or epic refine until adoption core_ready. "
            "Status only — never auto-apply without human/agent explicit apply."
            + quiet
        )
        return {
            "next_action": action,
            "prompt_segment": prompt,
            "rationale": (
                f"adoption core_ready=false; "
                f"minutes_remaining={mins} (#937/#935/#633)"
            ),
            "state_snapshot": state,
            "agent_type": agent_type or "general",
            "priority": "adoption",
            "next_command": next_cmd,
            "estimated_minutes_remaining": mins,
            "within_30m_budget": adopt.get("within_30m_budget"),
            "ask_user_question": adopt.get("ask_user_question"),
        }

    # 6b) Core adoption ready but first Q&A seed pending (#949/#633)
    first_qa = adopt.get("first_qa") if adopt else None
    if (
        adopt
        and adopt.get("core_ready") is True
        and isinstance(first_qa, dict)
        and first_qa.get("seeded") is False
    ):
        next_cmd = "gh plate adopt --first-qa-plan --json"
        return {
            "next_action": f"seed first Q&A after adoption: {next_cmd}",
            "prompt_segment": (
                "Local adoption core_ready but first Q&A Questions not seeded (#949/#633). "
                "1) `gh plate adopt --first-qa-plan --json` / plate_adoption_first_qa_plan  "
                "2) Review 3 starter Curiosity Questions; apply only with explicit runner  "
                "3) Then `gh plate feed --json` / product planning. "
                "Dry-run default — no GitHub issue create without injectable runner."
                + quiet
            ),
            "rationale": "adoption core_ready; first_qa.seeded=false (#949/#935/#633)",
            "state_snapshot": state,
            "agent_type": agent_type or "general",
            "priority": "first_qa_seed",
            "next_command": next_cmd,
            "ask_user_question": {
                "question": "Seed 3 starter Curiosity Questions for first Q&A?",
                "options": [
                    {
                        "label": "First Q&A seed plan",
                        "description": next_cmd,
                    },
                    {"label": "Open feed", "description": "gh plate feed --json"},
                    {"label": "Defer", "description": "Continue without seed"},
                ],
            },
        }

    # 7) Self-migrate pin/payload drift — plan before new Features (#941/#649)
    if self_migrate_drift:
        target = smig.get("target_version") or "?"
        next_cmd = str(
            smig.get("next_command") or "gh plate self-migrate --plan --json"
        )
        pin = (smig.get("pin") or {}).get("version")
        action = (
            f"review self-migrate plan (pin={pin} → target={target}): {next_cmd}"
        )
        prompt = (
            "Local plate-core pin/payload drift detected (#939/#649). "
            "1) `gh plate self-migrate --plan --json` / plate_self_migrate_plan  "
            "2) Review steps (upgrade pin, import-payload conservative, health)  "
            "3) Apply only with explicit approval — plan is dry-run only. "
            "Do not start ready Feature work until drift is resolved or deferred."
            + quiet
        )
        return {
            "next_action": action,
            "prompt_segment": prompt,
            "rationale": (
                f"self_migrate drift=true pin={pin} target={target} "
                f"(#941/#939/#649)"
            ),
            "state_snapshot": state,
            "agent_type": agent_type or "general",
            "priority": "self_migrate",
            "next_command": next_cmd,
            "target_version": target,
            "risk": smig.get("risk"),
            "ask_user_question": smig.get("ask_user_question"),
        }

    # 7b) Post-migrate verify residual — pin aligned but ready=false (#969/#965/#649)
    if self_migrate_not_ready:
        target = smig.get("target_version") or "?"
        next_cmd = str(
            smig.get("next_command") or "gh plate self-migrate --verify --json"
        )
        failures = list(smig.get("failures") or [])
        fail_s = ",".join(str(f) for f in failures) if failures else "not_ready"
        action = f"run post-migrate verify ({fail_s}): {next_cmd}"
        prompt = (
            "Self-migrate pin/payload looks aligned but offline verify is not ready "
            "(#965/#969/#649). "
            "1) `gh plate self-migrate --verify --json` / plate_self_migrate_verify  "
            "2) Address failures (adoption, .plate validity) then re-verify  "
            "3) `gh plate health` for remote signals. "
            "Do not start ready Feature work until verify ready or explicitly deferred."
            + quiet
        )
        return {
            "next_action": action,
            "prompt_segment": prompt,
            "rationale": (
                f"self_migrate ready=false failures={fail_s} target={target} "
                f"(#969/#965/#649)"
            ),
            "state_snapshot": state,
            "agent_type": agent_type or "general",
            "priority": "self_migrate_verify",
            "next_command": next_cmd,
            "target_version": target,
            "failures": failures,
            "ask_user_question": smig.get("ask_user_question"),
        }

    # 7c) Concrete ready Feature/Bug — prefer over generic epic text (#793)
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

    # 6) Active scheduled op runs (blocked/running/planned) — ceremony attention (#933)
    if active_sop_runs:
        first = active_sop_runs[0]
        oid = str(first.get("op_id") or first.get("id") or "unknown")
        st = str(first.get("status") or "active")
        action = f"advance scheduled op run [{st}]: {oid}"
        prompt = (
            f"Active scheduled op needs attention: `{oid}` status={st} (#641/#659). "
            f"1) `gh plate scheduled-ops --status` / plate_scheduled_ops_status  "
            f"2) dry-run plan: `gh plate scheduled-ops --plan {oid}`  "
            f"3) For blocked high-impact: checkpoint approve + shadow_ack before live  "
            f"4) Complete via plate_scheduled_op_complete when done. "
            f"risk_tolerance=off still allows dry-run plan/status."
            + quiet
        )
        return {
            "next_action": action,
            "prompt_segment": prompt,
            "rationale": f"{len(active_sop_runs)} active scheduled op run(s) (#933/#659)",
            "state_snapshot": state,
            "agent_type": agent_type or "general",
            "priority": "scheduled_op",
            "op_id": oid,
            "scheduled_op_status": st,
            "active_scheduled_ops": [
                {
                    "op_id": r.get("op_id") or r.get("id"),
                    "status": r.get("status"),
                }
                for r in active_sop_runs[:10]
            ],
        }

    # 7) Project Manager orchestrator (#660) — empty pipeline prefers PM over generic epic
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

    # 8) Runnable scheduled ops (dry-run plan) when pipeline + PM idle (#933/#659)
    if runnable_sops:
        first = runnable_sops[0]
        oid = str(first.get("id") or first.get("op_id") or "unknown")
        action = f"dry-run plan next runnable scheduled op: {oid}"
        prompt = (
            f"Empty pipeline and idle PM; scheduled catalog has "
            f"{len(runnable_sops)} op(s) runnable at current risk_tolerance (#933/#641). "
            f"Start with dry-run: `gh plate scheduled-ops --plan {oid}` / "
            f"plate_scheduled_op_plan, then `--run` only if dry_run and gates allow. "
            f"High/critical still need shadow_ack + approval. Prefer ceremony prep "
            f"(release-cut-prep) over deploy/marketplace human Tasks."
            + quiet
        )
        return {
            "next_action": action,
            "prompt_segment": prompt,
            "rationale": (
                f"{len(runnable_sops)} runnable scheduled op(s) at risk_tolerance "
                f"(#933/#659)"
            ),
            "state_snapshot": state,
            "agent_type": agent_type or "general",
            "priority": "scheduled_ops_plan",
            "op_id": oid,
            "runnable_scheduled_ops": [
                {"id": o.get("id") or o.get("op_id"), "risk_level": o.get("risk_level")}
                for o in runnable_sops[:10]
            ],
        }

    # 9) Open Epics, PM idle, no ready issues — closeouts / stub refine (#905/#909)
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
            # No complete-child candidates — first-slices recorded (#915/#913) → v1 residual (#981)
            # Do not keep agents in "refine stub Feature" loops when only deferred work remains
            # (e.g. browser #661) and real next gates are human E2E / marketplace Tasks.
            action = (
                "v1.0 agent first-slices landed: clear human-gated #654 residuals "
                "(live E2E proof and/or marketplace/PyPI Tasks); do not implement deferred browser #661"
            )
            prompt = (
                "Pipeline empty, PM idle, no ready Features/Bugs, and no complete-child "
                "Epic closeout candidates (#915; status:implemented Epics skipped per #913). "
                "Core Phase 0–3 first-slice surfaces are recorded on "
                "docs/wiki/V1-Autonomy-Surfaces-Epic-Closeouts.md. "
                "1) Do **not** re-sketch first slices or start deferred browser #661. "
                "2) Human-gated: live under-30m adopter E2E and/or Tasks #380/#381/#625/#626 "
                "(agents never complete those). "
                "3) Optional: `gh plate release status` + review unreleased fragments; "
                "do not cut v1.0.0 without #654 checklist E2E. "
                "4) Only refine a non-deferred stub if a human explicitly scopes it."
                + quiet
            )
            rationale = (
                f"{open_epics} open Epic(s); 0 closeout candidates — "
                f"v1 residual / human gates (#981/#915/#913)"
            )
        out: dict[str, Any] = {
            "next_action": action,
            "prompt_segment": prompt,
            "rationale": rationale,
            "state_snapshot": state,
            "agent_type": agent_type or "general",
            "priority": "v1_residual" if not structured else "epic",
        }
        if structured:
            out["priority"] = "epic"
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
    include_scheduled_ops: bool = True,
    include_adoption: bool = True,
    include_self_migrate: bool = True,
) -> dict[str, Any]:
    """Live what-next: health + budget + PRs + adoption + self-migrate + ready issues + PM + release + scheduled ops."""
    health: dict[str, Any] = {}
    budget: dict[str, Any] = {}
    open_prs: list[dict[str, Any]] = []
    ready_issues: list[dict[str, Any]] = []
    pending_fragment_count: int | None = None
    pm_status: dict[str, Any] | None = None
    release_status: dict[str, Any] | None = None
    scheduled_ops: dict[str, Any] | None = None
    adoption: dict[str, Any] | None = None
    self_migrate: dict[str, Any] | None = None

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
    adoption_session: dict[str, Any] | None = None
    if include_adoption and not open_prs:
        try:
            from .adoption import assess_adoption_readiness

            adoption = assess_adoption_readiness(".", include_optional=False)
        except Exception:
            adoption = None
        try:
            from .adoption import adoption_session_status

            adoption_session = adoption_session_status(".")
        except Exception:
            adoption_session = None

    # Only when adoption is ready (or skipped) — pin drift is secondary to first adopt.
    # Active session also blocks self-migrate ranking (session path wins in recommend).
    session_active = bool(
        isinstance(adoption_session, dict) and adoption_session.get("active") is True
    )
    adopt_ready = (
        (adoption is None or adoption.get("core_ready") is not False)
        and not session_active
    )
    if include_self_migrate and not open_prs and adopt_ready:
        try:
            from .self_migrate import verify_self_migrate

            # Prefer verify report (#969): includes drift + ready + failures offline.
            _sm = verify_self_migrate(".", include_payload=True)
            migrate = (_sm or {}).get("migrate") or {}
            self_migrate = {
                "drift": bool(migrate.get("drift")),
                "target_version": migrate.get("target_version"),
                "pin": migrate.get("pin"),
                "risk": migrate.get("risk"),
                "ready": (_sm or {}).get("ready"),
                "failures": list((_sm or {}).get("failures") or []),
                "next_command": (_sm or {}).get("next_command"),
                "ask_user_question": (_sm or {}).get("ask_user_question"),
                "installed_version": migrate.get("installed_version"),
            }
        except Exception:
            self_migrate = None

    if include_scheduled_ops and not open_prs and not ready_issues:
        try:
            from .scheduled_ops import (
                list_op_runs,
                scheduled_ops_status,
            )

            risk = str(
                (budget or {}).get("risk_tolerance")
                or health.get("budget_risk_tolerance")
                or "off"
            )
            st = scheduled_ops_status(risk_tolerance=risk, include_budget=False)
            active_runs = [
                r
                for r in list_op_runs(status="all", limit=20)
                if r.get("status") in ("blocked", "running", "planned")
            ]
            scheduled_ops = {
                **st,
                "active_runs": active_runs,
            }
        except Exception:
            scheduled_ops = None

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
        scheduled_ops=scheduled_ops,
        adoption=adoption,
        adoption_session=adoption_session,
        self_migrate=self_migrate,
    )
