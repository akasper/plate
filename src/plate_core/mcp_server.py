"""Minimal MCP stdio server for plate_core v1 baseline."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict

from . import __version__
from .baseline_catalog import (
    BaselineCatalogError,
    delegate_to_agent,
    get_agent,
    get_informational_goal,
    get_skill,
    list_agents,
    list_informational_goals,
    list_skills,
)
from .bootstrap import run_bootstrap
from .context_map import get_context_route, list_context_routes
from .epics import get_epic_status
from .features import get_features
from .health import get_health
from .mcp.tools import InitPlaywrightTool, RecordE2eGifTool, ValidateE2eTestsTool
from .pr_babysit import babysit_pr, get_actionable_review_threads, get_pr_merge_gates, resolve_review_thread
from .plate_config import apply_plate_config_upgrade, get_plate_config_report, init_plate_config
from .release import (
    cleanup_dead_branches,
    get_release_notes_diff,
    get_release_status,
    get_release_target_epic_guidance,
)
from .migration import generate_migration_plan, apply_migration_plan
from .contemplation import ContemplationEngine, trigger_contemplation
from .costs import get_cost_report
from .autonomy import get_autonomy_status, run_autonomy_cycle
from .checkpoint import (
    create_checkpoint,
    decide_checkpoint,
    get_checkpoint,
    list_checkpoints,
    list_open_checkpoints,
)
from .ledger import get_decision, list_decisions, query_decisions, record_decision, ledger_summary
from .feed import get_user_feed
from .planning import (
    apply_planning_answer,
    build_plan_from_session,
    get_planning_script,
    start_planning_session,
)
from .epic_release_planning import (
    apply_er_answer,
    build_er_plan_from_session,
    get_er_script,
    start_er_session,
)
from .design_research_approval import (
    decide_proposal,
    get_proposal,
    list_authoritative,
    list_proposals,
    propose_artifact,
)
from .pm import (
    assign_work,
    complete_pm_assignment,
    get_pm_status,
    list_pm_queue,
    list_team,
    run_pm_cycle,
    run_pm_loop,
)
from .discussions import (
    add_discussion_comment,
    create_discussion,
    get_discussion,
    list_discussion_categories,
    list_discussion_comments,
    list_discussions,
    list_open_ideas,
)
from .mcp.curiosity_tools import (
    CURIOSITY_TOOLS,
    CreateBlockingQuestionTool,
    GetAnswersTool,
    GetQuestionTool,
    ListQuestionsTool,
    RecordAnswerTool,
    SynthesizePrioritiesTool,
)


def _write(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def _plan_epic_stub(args: dict) -> object:
    """Risk-aware epic planning (replaces pure Phase-1 stub per #477 / Epic #470).
    Loads autonomy.risk_tolerance from .plate. At 'high' tolerance, auto-proposes
    more child stubs (with need:refinement) derived from health/Goals signals.
    Returns plan + proposed_children; host (or engine) performs creation + sub_issue links
    via GH surfaces for full auditability. Quiet ops and budget gates apply upstream.
    """
    try:
        from .plate_config import load_plate_config
        conf = load_plate_config()
        tol = (getattr(conf, "autonomy", None) or {}).get("risk_tolerance", "medium")
    except Exception:
        tol = "medium"

    base_children = {
        "research": ["Budget/observability gaps", "Procedure extensions"],
        "design": ["Contract refinements"],
        "feature": ["plate_plan_epic risk-aware", "full procedure dispatch"],
    }
    if tol == "high":
        base_children["research"].extend(["Goals-driven drift", "Long-running scheduler integration"])
        base_children["feature"].extend(["auto-stub from info_audit", "risk-tiered delegation"])
    if tol == "off":
        base_children = {"research": [], "design": [], "feature": []}

    class _Stub:
        def to_dict(self) -> dict:
            return {
                "tool": "plate_plan_epic",
                "status": "ok",
                "input_received": {k: v for k, v in args.items()},
                "risk_tolerance": tol,
                "planning_schema": {
                    "epic": {"title": None, "problem_statement": None, "acceptance_criteria": [], "scope_in": [], "scope_out": [], "dependencies": []},
                    "session_state": {"turn": 0, "phase": "proposal" if tol != "off" else "manual"},
                    "child_issues": base_children,
                },
                "proposed_children": [
                    {"type": t, "title": f"{t.title()}: {item}", "labels": [t.title(), "need:refinement"], "parent": 470}
                    for t, items in base_children.items() for item in items
                ] if tol != "off" else [],
                "note": "Risk-aware planner (high tol auto-generates more need:refinement children from Goals/audit signals). Creation + linking via host GH MCP (issue_write + sub_issue_write) for GitHub truth. See design doc and Epic #470.",
            }
    return _Stub()


def _what_next(repo: str | None, agent_type: str | None = None) -> dict:
    """v1 static What Next? for PLATE process (Epic #282 / #285).

    Uses live health + simple heuristics over documented flows (epics, labels, fragments, Goals).
    Returns next recommended action + prompt segment for agent use.
    """
    try:
        from .health import get_health
        h = get_health(repo).to_dict() if repo or True else {}
        labels_ok = h.get("label_coverage_ok", False)
        open_epics = h.get("open_epic_count", 0)
        # simplistic v1
        if not labels_ok:
            action = "run bootstrap to establish labels/wiki/epic/starters"
            prompt = (
                "Follow the PLATE bootstrap flow: create required labels, enable wiki, seed initial Epic, "
                "seed starter Questions from catalog. Then create a Goals wiki page per convention and use it for audits. "
                "For any looped execution, use terse one-sentence bullet turn summaries and post comments only on meaningful progress (quiet_operations guidance)."
            )
        elif open_epics > 0:
            action = "advance an open Epic: pick a child Feature/Bug with tests sketched, no need:refinement"
            prompt = (
                "Use plate_epic_status or gh plate epic status to list children. For a Feature: read full issue, "
                "add/update tests first, implement smallest change, author fragment in .agentic/releases/unreleased/, "
                "PR with clean title + labels (Feature + area + Epic:*) + Closes #N in body only, babysit with gh plate pr babysit. "
                "In loops: terse bullet turn summaries only; comments only on real progress per quiet_operations."
            )
        else:
            action = "check for pending release fragments or next beta item"
            prompt = (
                "Run gh plate release status. If unreleased fragments, prepare for cut_release. "
                "Otherwise pick next beta-roadmap Feature (e.g. #260 local-rebase, #285 what-next, packaging, etc.). "
                "Looped runs: emit only terse one-sentence bullets for the turn; follow quiet comment rules."
            )
        return {
            "next_action": action,
            "prompt_segment": prompt,
            "rationale": "v1 heuristic on health (labels, open_epics); expand with full state (epics, fragments, Goals presence) in follow-ups",
            "state_snapshot": {"label_coverage_ok": labels_ok, "open_epic_count": open_epics},
            "agent_type": agent_type or "general",
        }
    except Exception as exc:
        return {"next_action": "inspect with plate_health + plate_epic_status", "error": str(exc)}


def _handle_tools_call(req_id: object, params: dict) -> None:
    name = params.get("name")
    args = params.get("arguments", {}) or {}

    try:
        if name == "plate_health":
            report = get_health(args.get("repo"))
            payload = report.to_dict()
        elif name == "plate_epic_status":
            report = get_epic_status(args.get("repo"))
            payload = report.to_dict()
        elif name == "init_playwright":
            payload = InitPlaywrightTool.execute(
                args.get("repo_path", "."),
                args.get("template_repo"),
                bool(args.get("force", False)),
            )
        elif name == "record_e2e_gif":
            test_name = args.get("test_name")
            if not test_name:
                raise ValueError("test_name is required")
            payload = RecordE2eGifTool.execute(
                args.get("repo_path", "."),
                test_name,
                args.get("quality", "medium"),
            )
        elif name == "validate_e2e_tests":
            payload = ValidateE2eTestsTool.execute(args.get("repo_path", "."))
        elif name == "plate_agents":
            payload = {"agents": [agent.to_dict() for agent in list_agents()]}
        elif name == "plate_agent":
            payload = get_agent(args.get("agent_id")).to_dict()
        elif name == "plate_skills":
            payload = {"skills": [skill.to_dict() for skill in list_skills()]}
        elif name == "plate_skill":
            payload = get_skill(args.get("skill_id")).to_dict()
        elif name == "plate_contexts":
            payload = {"contexts": [route.to_dict() for route in list_context_routes()]}
        elif name == "plate_context":
            payload = get_context_route(args.get("context_id")).to_dict()
        elif name == "plate_delegate_to_agent":
            agent_id = args.get("agent_id")
            task_description = args.get("task_description")
            if not agent_id:
                raise ValueError("agent_id is required")
            if not task_description:
                raise ValueError("task_description is required")
            payload = delegate_to_agent(agent_id, task_description).to_dict()
        elif name == "plate_features":
            payload = get_features(args.get("repo")).to_dict()
        elif name == "plate_bootstrap":
            payload = run_bootstrap(args.get("repo"), apply_mode=bool(args.get("apply", False))).to_dict()
        elif name == "plate_config_get":
            payload = get_plate_config_report(args.get("repo_root")).to_dict()
        elif name == "plate_config_validate":
            payload = get_plate_config_report(args.get("repo_root")).to_dict()
        elif name == "plate_config_init":
            payload = init_plate_config(args.get("repo_root"), force=bool(args.get("force", False))).to_dict()
        elif name == "plate_config_upgrade":
            payload = apply_plate_config_upgrade(
                args.get("repo_root"),
                apply=bool(args.get("apply", False)),
            ).to_dict()
        elif name == "plate_plan_epic":
            payload = _plan_epic_stub(args).to_dict()
        elif name == "plate_planning_start":
            payload = start_planning_session(str(args.get("kind") or "feature"))
        elif name == "plate_planning_answer":
            session = args.get("session") or {}
            if isinstance(session, str):
                try:
                    session = json.loads(session)
                except Exception:
                    session = {}
            payload = apply_planning_answer(
                session if isinstance(session, dict) else {},
                str(args.get("answer") or args.get("answer_text") or ""),
                question_id=args.get("question_id"),
            )
        elif name == "plate_planning_build":
            session = args.get("session") or {}
            if isinstance(session, str):
                try:
                    session = json.loads(session)
                except Exception:
                    session = {}
            payload = build_plan_from_session(session if isinstance(session, dict) else {})
        elif name == "plate_planning_script":
            payload = get_planning_script(str(args.get("kind") or "feature"))
        elif name == "plate_er_planning_start":
            payload = start_er_session(str(args.get("kind") or "epic"))
        elif name == "plate_er_planning_answer":
            session = args.get("session") or {}
            if isinstance(session, str):
                try:
                    session = json.loads(session)
                except Exception:
                    session = {}
            payload = apply_er_answer(
                session if isinstance(session, dict) else {},
                str(args.get("answer") or args.get("answer_text") or ""),
                question_id=args.get("question_id"),
            )
        elif name == "plate_er_planning_build":
            session = args.get("session") or {}
            if isinstance(session, str):
                try:
                    session = json.loads(session)
                except Exception:
                    session = {}
            payload = build_er_plan_from_session(session if isinstance(session, dict) else {})
        elif name == "plate_er_planning_script":
            payload = get_er_script(str(args.get("kind") or "epic"))
        elif name == "plate_artifact_propose":
            payload = propose_artifact(
                kind=str(args.get("kind") or "design"),
                title=str(args.get("title") or "Artifact"),
                summary=str(args.get("summary") or ""),
                content_path=str(args.get("content_path") or ""),
                content_excerpt=str(args.get("content_excerpt") or ""),
                related_issue=args.get("related_issue"),
                related_epic=args.get("related_epic"),
                originating_question=args.get("originating_question"),
                media_links=list(args.get("media_links") or []),
                actor=str(args.get("actor") or "agent"),
            )
        elif name == "plate_artifact_decide":
            payload = decide_proposal(
                str(args.get("proposal_id") or args.get("id") or ""),
                str(args.get("decision") or ""),
                decided_by=str(args.get("decided_by") or "human"),
                note=str(args.get("note") or ""),
            )
        elif name == "plate_artifact_list":
            if args.get("authoritative"):
                payload = {"proposals": list_authoritative(kind=args.get("kind"))}
            else:
                payload = {
                    "proposals": list_proposals(
                        status=args.get("status") or "pending",
                        kind=args.get("kind"),
                        limit=int(args.get("limit") or 50),
                    )
                }
        elif name == "plate_artifact_get":
            payload = get_proposal(str(args.get("proposal_id") or args.get("id") or "")) or {
                "error": "not found"
            }
        elif name == "plate_pr_babysit":
            pr_number = args.get("pr_number")
            if pr_number is None:
                raise ValueError("pr_number is required")
            pr_number = int(pr_number)
            if pr_number <= 0:
                raise ValueError("pr_number must be > 0")
            payload = babysit_pr(
                pr_number=pr_number,
                repo=args.get("repo"),
                agent_logins=args.get("agents"),
                act=bool(args.get("act", False)),
                branch_update_strategy=args.get("branch_update_strategy"),
                pr_review_scope=args.get("scope") or args.get("pr_review_scope"),
            ).to_dict()
        elif name == "plate_get_pr_merge_gates":
            pr_number = args.get("pr_number")
            if pr_number is None:
                raise ValueError("pr_number is required")
            pr_number = int(pr_number)
            if pr_number <= 0:
                raise ValueError("pr_number must be > 0")
            payload = get_pr_merge_gates(
                pr_number=pr_number,
                repo=args.get("repo"),
            )
        elif name == "plate_resolve_review_thread":
            thread_id = args.get("thread_id")
            if not thread_id:
                raise ValueError("thread_id is required")
            payload = resolve_review_thread(
                thread_id=thread_id,
                repo=args.get("repo"),
            )
        elif name == "plate_get_actionable_review_threads":
            # High-level listing helper (encapsulates GraphQL pagination, DBID, filtering).
            # Part of review thread encapsulation for #516.
            payload = {
                "repo": args.get("repo"),
                "pr_number": args.get("pr_number"),
                "threads": get_actionable_review_threads(
                    pr_number=args.get("pr_number"),
                    repo=args.get("repo"),
                    agent_logins=args.get("agent_logins"),
                    pr_review_scope=args.get("scope") or args.get("pr_review_scope"),
                ),
            }
        elif name == "plate_what_next":
            # What Next? (Epic #282 / #285 v1 static)
            # Uses live state (health, epics, fragments, labels) to pick next PLATE step and prompt segment.
            # For v1: simple decision tree over common paths; future data-driven.
            payload = _what_next(args.get("repo"), args.get("agent_type"))
        elif name == "plate_feed":
            payload = get_user_feed(
                repo=args.get("repo"),
                limit=int(args.get("limit") or 10),
                include_process=bool(args.get("include_process", True)),
                include_autonomy=bool(args.get("include_autonomy", True)),
            )
        elif name == "plate_contemplate":
            # Contemplation Engine entrypoint (Epic #139 / Feature #149 minimal slice)
            qn = args.get("question_number")
            if not qn:
                raise ValueError("question_number is required")
            payload = trigger_contemplation(
                question_number=qn,
                answer_text=args.get("answer_text", ""),
                repo=args.get("repo"),
                session=args.get("session"),
                source=args.get("source", "contemplation"),
                answered_by=args.get("answered_by", "engine"),
            )
        elif name in CURIOSITY_TOOLS:
            # Curiosity / Q&A Mode tools (Epic #139 / Feature #154)
            tool_cls = CURIOSITY_TOOLS[name]
            # Pass through common args + any tool-specific ones
            payload = tool_cls.execute(**args)
        elif name == "plate_release_status":
            from pathlib import Path
            releases_dir_arg = args.get("releases_dir")
            payload = get_release_status(
                repo=args.get("repo"),
                releases_dir=Path(releases_dir_arg) if releases_dir_arg else None,
            ).to_dict()
        elif name == "plate_release_target_epic":
            payload = get_release_target_epic_guidance(
                epic_number=int(args.get("epic_number")),
                repo=args.get("repo"),
            ).to_dict()
        elif name == "plate_release_cleanup_branches":
            payload = cleanup_dead_branches(
                repo=args.get("repo"),
                base_branch=args.get("base_branch"),
                apply=bool(args.get("apply", False)),
                limit=args.get("limit"),
            ).to_dict()
        elif name == "plate_release_notes":
            from pathlib import Path
            releases_dir_arg = args.get("releases_dir")
            payload = get_release_notes_diff(
                from_version=args.get("from_version"),
                to_version=args.get("to_version"),
                releases_dir=Path(releases_dir_arg) if releases_dir_arg else None,
            ).to_dict()
        elif name == "plate_costs":
            if args.get("dashboard"):
                from .costs import get_cost_dashboard
                payload = get_cost_dashboard(
                    repo=args.get("repo"),
                    epic_label=args.get("epic_label"),
                )
            else:
                payload = get_cost_report(
                    repo=args.get("repo"),
                    epic_label=args.get("epic_label"),
                ).to_dict()
        elif name == "plate_autonomy_status":
            payload = get_autonomy_status(args.get("repo"))
        elif name == "plate_pm_status":
            payload = get_pm_status(args.get("repo"))
        elif name == "plate_pm_team":
            payload = {"team": list_team()}
        elif name == "plate_pm_assign":
            item = args.get("item") or {}
            if isinstance(item, str):
                try:
                    item = json.loads(item)
                except Exception:
                    item = {"title": item}
            st = get_autonomy_status(args.get("repo"))
            payload = assign_work(
                item if isinstance(item, dict) else {"title": str(item)},
                risk_tolerance=str(st.get("risk_tolerance") or "medium"),
                budget_remaining=st.get("budget_remaining_tokens"),
            )
        elif name == "plate_pm_run_cycle":
            payload = run_pm_cycle(
                repo=args.get("repo"),
                dry_run=bool(args.get("dry_run", True)),
                max_assignments=int(args.get("max_assignments") or 5),
            )
        elif name == "plate_pm_run_loop":
            payload = run_pm_loop(
                repo=args.get("repo"),
                dry_run=bool(args.get("dry_run", True)),
                max_cycles=int(args.get("max_cycles") or 3),
                max_assignments=int(args.get("max_assignments") or 5),
            )
        elif name == "plate_pm_queue":
            payload = {
                "assignments": list_pm_queue(
                    repo=args.get("repo"),
                    status=args.get("status"),
                    limit=int(args.get("limit") or 50),
                )
            }
        elif name == "plate_pm_complete":
            payload = complete_pm_assignment(
                str(args.get("assignment_id") or ""),
                status=str(args.get("status") or "done"),
                note=str(args.get("note") or ""),
                repo=args.get("repo"),
            )
        elif name == "plate_ledger_record":
            payload = record_decision(
                action_kind=str(args.get("action_kind") or "unknown"),
                decision=str(args.get("decision") or "proceed"),
                reason=str(args.get("reason") or ""),
                sources=list(args.get("sources") or []),
                cost_estimate_tokens=args.get("cost_estimate_tokens"),
                risk_tolerance=str(args.get("risk_tolerance") or ""),
                impact=str(args.get("impact") or ""),
                related_issue=args.get("related_issue"),
                related_pr=args.get("related_pr"),
                shadow_id=args.get("shadow_id"),
                checkpoint_id=args.get("checkpoint_id"),
                artifact_links=list(args.get("artifact_links") or []),
                actor=str(args.get("actor") or "agent"),
                session=str(args.get("session") or ""),
                metadata=args.get("metadata") if isinstance(args.get("metadata"), dict) else {},
            )
        elif name == "plate_ledger_list":
            payload = {
                "decisions": list_decisions(
                    action_kind=args.get("action_kind"),
                    decision=args.get("decision"),
                    related_issue=args.get("related_issue"),
                    limit=int(args.get("limit") or 50),
                )
            }
        elif name == "plate_ledger_query":
            payload = {
                "decisions": query_decisions(
                    str(args.get("query") or ""),
                    limit=int(args.get("limit") or 50),
                )
            }
        elif name == "plate_ledger_get":
            payload = get_decision(str(args.get("decision_id") or args.get("id") or "")) or {
                "error": "not found"
            }
        elif name == "plate_ledger_summary":
            payload = ledger_summary(limit=int(args.get("limit") or 20))
        elif name == "plate_autonomy_run_cycle":
            max_steps = args.get("max_steps")
            if max_steps is not None:
                try:
                    max_steps = int(max_steps)
                except (ValueError, TypeError):
                    max_steps = None
            payload = run_autonomy_cycle(
                repo=args.get("repo"),
                dry_run=bool(args.get("dry_run", False)),
                max_steps=max_steps,
            )
        elif name == "plate_autonomy_list_procedures":
            from .autonomy import AutonomyEngine
            engine = AutonomyEngine(args.get("repo"))
            filtered = [
                p for p in engine.procedures
                if p.enabled and engine._risk_rank(p.risk_level) <= engine._risk_rank(engine.risk_tolerance)
            ]
            payload = {"procedures": [asdict(p) for p in filtered]}
        elif name == "plate_autonomy_run_procedure":
            from .autonomy import AutonomyEngine
            engine = AutonomyEngine(args.get("repo"))
            payload = engine.run_procedure(
                proc_id=args.get("proc_id"),
                dry_run=bool(args.get("dry_run", False)),
                shadow_ack=args.get("shadow_ack"),
                approved=bool(args.get("approved", False)),
                checkpoint_id=args.get("checkpoint_id"),
            )
        elif name == "plate_autonomy_simulate":
            from .autonomy import simulate_autonomy_action
            scope = args.get("scope") or {}
            if isinstance(scope, str):
                try:
                    scope = json.loads(scope)
                except Exception:
                    scope = {"raw": scope}
            payload = simulate_autonomy_action(
                action_kind=str(args.get("action_kind") or args.get("action") or "unknown"),
                repo=args.get("repo"),
                scope=scope if isinstance(scope, dict) else {},
            )
        elif name == "plate_checkpoint_create":
            from .autonomy import AutonomyEngine
            eng = AutonomyEngine(args.get("repo"))
            scope = args.get("scope") or {}
            if isinstance(scope, str):
                try:
                    scope = json.loads(scope)
                except Exception:
                    scope = {"raw": scope}
            payload = create_checkpoint(
                title=str(args.get("title") or "Human checkpoint"),
                reason=str(args.get("reason") or "Human judgment required"),
                impact=str(args.get("impact") or "medium"),
                action_kind=str(args.get("action_kind") or ""),
                scope=scope if isinstance(scope, dict) else {},
                shadow_id=args.get("shadow_id"),
                related_issue=args.get("related_issue"),
                related_pr=args.get("related_pr"),
                created_by=str(args.get("created_by") or "agent"),
                risk_tolerance=eng.risk_tolerance,
                autonomy_enabled=eng.enabled,
            )
        elif name == "plate_checkpoint_decide":
            payload = decide_checkpoint(
                checkpoint_id=str(args.get("checkpoint_id") or args.get("id") or ""),
                decision=str(args.get("decision") or ""),
                decided_by=str(args.get("decided_by") or "human"),
                note=str(args.get("note") or ""),
            )
        elif name == "plate_checkpoint_list":
            st = args.get("status") or "pending"
            if args.get("open_only"):
                payload = {"checkpoints": list_open_checkpoints(limit=int(args.get("limit") or 50))}
            else:
                payload = {
                    "checkpoints": list_checkpoints(
                        status=None if st == "all" else st,
                        limit=int(args.get("limit") or 50),
                    )
                }
        elif name == "plate_checkpoint_get":
            payload = get_checkpoint(str(args.get("checkpoint_id") or args.get("id") or "")) or {
                "error": "not found"
            }
        elif name == "plate_migrate_plan":
            plan = generate_migration_plan()
            if hasattr(plan, "to_dict"):
                payload = plan.to_dict()
            elif hasattr(plan, "__dict__"):
                payload = plan.__dict__
            else:
                payload = {"plan": str(plan)}
        elif name == "plate_migrate_apply":
            dry = bool(args.get("dry_run", True))
            plan = generate_migration_plan()
            results = apply_migration_plan(plan, dry_run=dry)
            payload = {"results": results, "dry_run": dry}
        elif name == "plate_perform_test_coverage_audit":
            from .mcp.audit_tools import PerformTestCoverageAuditTool
            payload = PerformTestCoverageAuditTool.execute(repo=repo, dry_run=args.get("dry_run", True))
        else:
            _write(
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Unknown tool: {name}"},
                }
            )
            return

        _write(
            {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(payload)}],
                    "isError": False,
                },
            }
        )
    except Exception as exc:
        _write(
            {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": str(exc)}],
                    "isError": True,
                },
            }
        )


def run() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        req = json.loads(line)
        req_id = req.get("id")
        method = req.get("method")

        if method == "initialize":
            _write(
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "serverInfo": {"name": "plate-mcp", "version": __version__},
                        "capabilities": {"tools": {}},
                    },
                }
            )
        elif method == "tools/list":
            _write(
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "tools": [
                            {
                                "name": "plate_health",
                                "description": "Return PLATE health summary for a repository.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "repo": {
                                            "type": "string",
                                            "description": "owner/name. Optional if running inside repo clone.",
                                        }
                                    },
                                },
                            },
                            {
                                "name": "plate_epic_status",
                                "description": "Return Epic and child issue summary for a repository.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "repo": {
                                            "type": "string",
                                            "description": "owner/name. Optional if running inside repo clone.",
                                        }
                                    },
                                },
                            },
                            {
                                "name": "init_playwright",
                                "description": "Initialize Playwright E2E testing in a repository.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "repo_path": {
                                            "type": "string",
                                            "description": "Path to target repository. Defaults to current directory.",
                                        },
                                        "template_repo": {
                                            "type": "string",
                                            "description": "Path to template source override. Defaults to plate payload in this repository.",
                                        },
                                        "force": {
                                            "type": "boolean",
                                            "description": "Overwrite existing tests/e2e/ directory. Defaults to false.",
                                        },
                                    },
                                    "required": [],
                                },
                            },
                            {
                                "name": "record_e2e_gif",
                                "description": "Record and generate a demo GIF from a Playwright E2E test.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "repo_path": {
                                            "type": "string",
                                            "description": "Path to repository with Playwright setup.",
                                        },
                                        "test_name": {
                                            "type": "string",
                                            "description": "Name of test to record (e.g., 'login', 'feature-flow').",
                                        },
                                        "quality": {
                                            "type": "string",
                                            "description": "Quality: 'low' (10fps), 'medium' (15fps), 'high' (30fps). Defaults to 'medium'.",
                                        },
                                    },
                                    "required": ["repo_path", "test_name"],
                                },
                            },
                            {
                                "name": "validate_e2e_tests",
                                "description": "Validate Playwright E2E setup and detect missing configuration.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "repo_path": {
                                            "type": "string",
                                            "description": "Path to repository. Defaults to current directory.",
                                        }
                                    },
                                    "required": [],
                                },
                            },
                            {
                                "name": "plate_agents",
                                "description": "Return the baseline agent catalog.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {},
                                    "required": [],
                                },
                            },
                            {
                                "name": "plate_agent",
                                "description": "Return one baseline agent by id.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "agent_id": {
                                            "type": "string",
                                            "description": "Baseline agent id.",
                                        }
                                    },
                                    "required": ["agent_id"],
                                },
                            },
                            {
                                "name": "plate_skills",
                                "description": "Return the baseline skill catalog.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {},
                                    "required": [],
                                },
                            },
                            {
                                "name": "plate_skill",
                                "description": "Return one baseline skill by id.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "skill_id": {
                                            "type": "string",
                                            "description": "Baseline skill id.",
                                        }
                                    },
                                    "required": ["skill_id"],
                                },
                            },
                            {
                                "name": "plate_contexts",
                                "description": "Return the canonical PLATE context-map routes used to decide where authoritative truth lives for a task.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {},
                                    "required": [],
                                },
                            },
                            {
                                "name": "plate_context",
                                "description": "Return one canonical PLATE context-map route by id.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "context_id": {
                                            "type": "string",
                                            "description": "Context route id.",
                                        }
                                    },
                                    "required": ["context_id"],
                                },
                            },
                            {
                                "name": "plate_features",
                                "description": "Return optional PLATE capability detection for a repository.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "repo": {
                                            "type": "string",
                                            "description": "owner/name. Optional if running inside repo clone.",
                                        }
                                    },
                                },
                            },
                            {
                                "name": "plate_bootstrap",
                                "description": "Plan or apply baseline PLATE bootstrap actions for a repository.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "repo": {
                                            "type": "string",
                                            "description": "owner/name. Optional if running inside repo clone.",
                                        },
                                        "apply": {
                                            "type": "boolean",
                                            "description": "When true, apply supported actions; default false (dry-run).",
                                        },
                                    },
                                },
                            },
                            {
                                "name": "plate_config_get",
                                "description": "Return effective local .plate configuration state for the current repository or repo_root.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "repo_root": {
                                            "type": "string",
                                            "description": "Optional local repository root path. Defaults to current directory.",
                                        }
                                    },
                                },
                            },
                            {
                                "name": "plate_config_validate",
                                "description": "Validate local .plate configuration and return the effective report shape.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "repo_root": {
                                            "type": "string",
                                            "description": "Optional local repository root path. Defaults to current directory.",
                                        }
                                    },
                                },
                            },
                            {
                                "name": "plate_config_init",
                                "description": "Create a baseline root .plate configuration file if missing (or overwrite with force).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "repo_root": {
                                            "type": "string",
                                            "description": "Optional local repository root path. Defaults to current directory.",
                                        },
                                        "force": {
                                            "type": "boolean",
                                            "description": "Overwrite an existing .plate file when true.",
                                        }
                                    },
                                },
                            },
                            {
                                "name": "plate_config_upgrade",
                                "description": "Upgrade an existing local .plate file to the current schema version, optionally writing it back to disk.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "repo_root": {
                                            "type": "string",
                                            "description": "Optional local repository root path. Defaults to current directory.",
                                        },
                                        "apply": {
                                            "type": "boolean",
                                            "description": "When true, write the upgraded .plate file back to disk.",
                                        }
                                    },
                                },
                            },
                            {
                                "name": "plate_plan_epic",
                                "description": "Risk-aware epic planning (replaces stub). Returns plan + proposed children (more at high autonomy.risk_tolerance, with need:refinement labels). Host performs creation/linking. Per #477 / Epic #470.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "repo": {
                                            "type": "string",
                                            "description": "owner/name. Optional if running inside repo clone.",
                                        },
                                        "session_state": {
                                            "type": "object",
                                            "description": "Optional resumption state from a prior planning session.",
                                        },
                                    },
                                },
                            },
                            {
                                "name": "plate_planning_start",
                                "description": "Start Q&A-driven feature (#630) or product (#628) planning session. Returns first question for ask_user_question.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "kind": {"type": "string", "description": "feature | product"},
                                    },
                                },
                            },
                            {
                                "name": "plate_planning_answer",
                                "description": "Record one planning answer and return next question or complete session (#628/#630).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "session": {"type": "object", "description": "Session dict from start/answer."},
                                        "answer": {"type": "string"},
                                        "question_id": {"type": "string"},
                                    },
                                    "required": ["session", "answer"],
                                },
                            },
                            {
                                "name": "plate_planning_build",
                                "description": "Build Feature or product Epic stub plan from completed session answers for human approval (#628/#630).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "session": {"type": "object"},
                                    },
                                    "required": ["session"],
                                },
                            },
                            {
                                "name": "plate_planning_script",
                                "description": "Return the ordered planning question script for feature or product kind.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "kind": {"type": "string"},
                                    },
                                },
                            },
{
                                "name": "plate_er_planning_start",
                                "description": "Start Q&A epic (#640) or release (#629) planning session. Returns first ask_user_question prompt.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "kind": {"type": "string", "description": "epic | release"},
                                    },
                                },
                            },
{
                                "name": "plate_er_planning_answer",
                                "description": "Record one epic/release planning answer; return next question or complete.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "session": {"type": "object"},
                                        "answer": {"type": "string"},
                                        "question_id": {"type": "string"},
                                    },
                                    "required": ["session", "answer"],
                                },
                            },
{
                                "name": "plate_er_planning_build",
                                "description": "Build Epic tree or Release plan from session for human approval (#640/#629).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "session": {"type": "object"},
                                    },
                                    "required": ["session"],
                                },
                            },
{
                                "name": "plate_er_planning_script",
                                "description": "Return ordered epic or release planning questions.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "kind": {"type": "string"},
                                    },
                                },
                            },
{
                                "name": "plate_artifact_propose",
                                "description": "Propose a Design or Research artifact for human approval (#632). Durable under .agentic/approvals/.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "kind": {"type": "string", "description": "design | research"},
                                        "title": {"type": "string"},
                                        "summary": {"type": "string"},
                                        "content_path": {"type": "string"},
                                        "content_excerpt": {"type": "string"},
                                        "related_issue": {"type": "integer"},
                                        "related_epic": {"type": "integer"},
                                        "originating_question": {"type": "integer"},
                                        "media_links": {"type": "array", "items": {"type": "string"}},
                                        "actor": {"type": "string"},
                                    },
                                    "required": ["kind", "title", "summary"],
                                },
                            },
{
                                "name": "plate_artifact_decide",
                                "description": "Approve, revise, or reject a Design/Research proposal (#632).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "proposal_id": {"type": "string"},
                                        "decision": {"type": "string", "description": "approve|revise|reject"},
                                        "decided_by": {"type": "string"},
                                        "note": {"type": "string"},
                                    },
                                    "required": ["proposal_id", "decision"],
                                },
                            },
{
                                "name": "plate_artifact_list",
                                "description": "List pending (or authoritative) Design/Research approval proposals (#632).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "status": {"type": "string"},
                                        "kind": {"type": "string"},
                                        "authoritative": {"type": "boolean"},
                                        "limit": {"type": "integer"},
                                    },
                                },
                            },
{
                                "name": "plate_artifact_get",
                                "description": "Get one artifact approval proposal by id (#632).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "proposal_id": {"type": "string"},
                                    },
                                    "required": ["proposal_id"],
                                },
                            },
                            {
                                "name": "plate_pr_babysit",
                                "description": (
                                    "Inspect a pull request for unresolved review feedback (scope: all|bot-only|human-only per #496) "
                                    "and base branch sync state. Optionally post trigger comments and auto-resolve outdated threads (--act / act=true)."
                                ),
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "repo": {
                                            "type": "string",
                                            "description": "owner/name. Optional if running inside repo clone.",
                                        },
                                        "pr_number": {
                                            "type": "integer",
                                            "description": "Pull request number.",
                                        },
                                        "agents": {
                                            "type": "string",
                                            "description": "Optional comma-separated login allowlist (overrides scope).",
                                        },
                                        "scope": {
                                            "type": "string",
                                            "enum": ["all", "bot-only", "human-only"],
                                            "description": "pr_review_scope (#496). Default all (from .plate or built-in).",
                                        },
                                        "act": {
                                            "type": "boolean",
                                            "description": "When true, post trigger comments if issues detected and auto-resolve outdated threads.",
                                        },
                                        "branch_update_strategy": {
                                            "type": "string",
                                            "enum": ["copilot-request", "local-rebase", "none"],
                                            "description": (
                                                "How to handle out-of-sync base branch: copilot-request (default, triggers Copilot merge assist), "
                                                "local-rebase (local worktree rebase+push), or none (detect only)."
                                            ),
                                        },
                                    },
                                    "required": ["pr_number"],
                                },
                            },
                            {
                                "name": "plate_get_pr_merge_gates",
                                "description": "Get comprehensive merge gates status for a PR using the get_pr_merge_gates helper (merge state, threads, note with checklist). Complements plate_pr_babysit for full 'make mergeable' ownership per #526.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "repo": {
                                            "type": "string",
                                            "description": "owner/name. Optional if running inside repo clone.",
                                        },
                                        "pr_number": {
                                            "type": "integer",
                                            "description": "Pull request number.",
                                        },
                                    },
                                    "required": ["pr_number"],
                                },
                            },
                            {
                                "name": "plate_resolve_review_thread",
                                "description": "Resolve a pull request review thread via GitHub GraphQL resolveReviewThread.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "repo": {
                                            "type": "string",
                                            "description": "owner/name. Optional if running inside repo clone.",
                                        },
                                        "thread_id": {
                                            "type": "string",
                                            "description": "GraphQL node ID of the review thread to resolve.",
                                        },
                                    },
                                    "required": ["thread_id"],
                                },
                            },
                            {
                                "name": "plate_get_actionable_review_threads",
                                "description": "List actionable (unresolved, non-outdated) review threads for a PR under pr_review_scope (#496: all|bot-only|human-only; default all includes Copilot). High-level helper: GraphQL reviewThreads, databaseId, suggestion metadata. Use with plate_resolve_review_thread / plate_pr_babysit. Addresses #516/#496.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "repo": {
                                            "type": "string",
                                            "description": "owner/name. Optional if running inside repo clone.",
                                        },
                                        "pr_number": {
                                            "type": "integer",
                                            "description": "Pull request number.",
                                        },
                                        "agent_logins": {
                                            "type": "string",
                                            "description": "Comma-separated login allowlist (optional; overrides scope).",
                                        },
                                        "scope": {
                                            "type": "string",
                                            "enum": ["all", "bot-only", "human-only"],
                                            "description": "pr_review_scope (#496). Default all.",
                                        },
                                    },
                                    "required": ["pr_number"],
                                },
                            },
                            {
                                "name": "plate_what_next",
                                "description": "Returns the next recommended PLATE process step and a short prompt segment, based on live health/epics/labels/fragments/Goals. Use first for autonomous or looped flows; follow quiet turn-summary rules for long-running use.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "repo": {
                                            "type": "string",
                                            "description": "owner/name. Optional if running inside repo clone.",
                                        },
                                        "agent_type": {
                                            "type": "string",
                                            "description": "Optional hint for specialized guidance (general, coding, docs, etc.).",
                                        },
                                    },
                                },
                            },
                            {
                                "name": "plate_feed",
                                "description": "Ranked endless feed of open Questions + Tasks (plus process/autonomy signals) for native TUI/CLI presentation (#631). Prefer this for user-facing Q&A/Task surfacing.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "repo": {"type": "string", "description": "owner/name. Optional."},
                                        "limit": {"type": "integer", "description": "Max items (default 10)."},
                                        "include_process": {"type": "boolean", "description": "Include plate_what_next process item (default true)."},
                                        "include_autonomy": {"type": "boolean", "description": "Include open autonomy checkpoints (default true)."},
                                    },
                                },
                            },
                            {
                                "name": "plate_contemplate",
                                "description": "Run Contemplation on a Question answer: evaluates Answer signal checklist against cited evidence, appends audit log, and reports PR-ready state (or follow-ups). Engine always produces traceable markers; agents follow quiet comment rules for any additional prose.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "question_number": {"type": "integer", "description": "The Question being answered."},
                                        "answer_text": {"type": "string", "description": "The answer text (full transcript captured)."},
                                        "repo": {"type": "string", "description": "owner/name. Optional."},
                                        "session": {"type": "string", "description": "Session/turn for provenance."},
                                        "source": {"type": "string", "description": "qanda | agent-contemplation | blocking", "default": "contemplation"},
                                        "answered_by": {"type": "string", "description": "Actor. Defaults to 'engine'."},
                                    },
                                    "required": ["question_number", "answer_text"],
                                },
                            },
                            {
                                "name": "plate_delegate_to_agent",
                                "description": "Route a task to a baseline agent (by id) and return a narrow delegation packet (details, skills, constraints, short prompt). Always call with a short task_description per the plate persona. Packets include retrieval hints; keep responses scoped and quiet per guidance.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "agent_id": {
                                            "type": "string",
                                            "description": "Baseline agent id to delegate the task to.",
                                        },
                                        "task_description": {
                                            "type": "string",
                                            "description": "Free-text description of the task to delegate.",
                                        },
                                    },
                                    "required": ["agent_id", "task_description"],
                                },
                            },
                            # === Curiosity / Q&A Mode tools (Epic #139, Feature #154) ===
                            # See docs/design/qanda-mcp-cli-surfaces.md and docs/design/curiosity-answer-model.md
                            {
                                "name": "plate_list_questions",
                                "description": "List open Question issues (informational goals) with answer_signal hints. Use with synthesize_priorities before native Q&A presentation. When surfacing, use minimal front matter per quiet_operations guidance.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "repo": {
                                            "type": "string",
                                            "description": "owner/name. Optional if running inside repo clone.",
                                        },
                                        "state": {
                                            "type": "string",
                                            "description": "open or closed. Defaults to open.",
                                            "default": "open",
                                        },
                                        "limit": {
                                            "type": "integer",
                                            "description": "Max results (default 20).",
                                            "default": 20,
                                        },
                                    },
                                },
                            },
                            {
                                "name": "plate_get_question",
                                "description": "Fetch full details + recent comments + detected PLATE-ANSWER blocks for one Question issue. Powers answer lookup and blocking Question resumption flows.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "question_number": {
                                            "type": "integer",
                                            "description": "The GitHub issue number of the Question.",
                                        },
                                        "repo": {
                                            "type": "string",
                                            "description": "owner/name. Optional.",
                                        },
                                        "include_comments": {
                                            "type": "boolean",
                                            "description": "Include recent comments and answer block detection (default true).",
                                            "default": True,
                                        },
                                    },
                                    "required": ["question_number"],
                                },
                            },
                            {
                                "name": "plate_record_answer",
                                "description": "Persist an answer to a Question as a structured PLATE-ANSWER comment block (per Answer Model). This is the primary ingestion hook for Contemplation Engine (#149) and blocking Question resumption (#148). Returns the posted comment + block for logging.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "question_number": {"type": "integer", "description": "Target Question issue number."},
                                        "answer_text": {"type": "string", "description": "The user's or agent's answer text (never lost)."},
                                        "answered_by": {"type": "string", "description": "Username or agent id. Defaults to 'agent'."},
                                        "session": {"type": "string", "description": "Optional session/turn id for provenance."},
                                        "source": {"type": "string", "description": "qanda | agent-contemplation | manual | blocking", "default": "qanda"},
                                        "repo": {"type": "string", "description": "owner/name. Optional."},
                                        "agent_actions": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                            "description": "E.g. ['Created: #147', 'Updated wiki'] for Contemplation log.",
                                        },
                                    },
                                    "required": ["question_number", "answer_text"],
                                },
                            },
                            {
                                "name": "plate_get_answers",
                                "description": "Return answers for a Question. Prefers the fast committed docs/curiosity/answers.yml index (Answer Model #150); falls back to scanning PLATE-ANSWER comment blocks on the issue.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "question_number": {"type": "integer", "description": "The Question issue number."},
                                        "repo": {"type": "string", "description": "owner/name. Optional."},
                                    },
                                    "required": ["question_number"],
                                },
                            },
                            {
                                "name": "plate_synthesize_priorities",
                                "description": "Return a ranked list of open Questions with rationale (heuristic v1). Use before native Q&A presentation or gh plate qanda. Prefer minimal framing when surfacing questions (see quiet_operations guidance).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "repo": {"type": "string", "description": "owner/name. Optional."},
                                        "max_results": {"type": "integer", "description": "Top N to return (default 5).", "default": 5},
                                    },
                                },
                            },
                            {
                                "name": "plate_create_blocking_question",
                                "description": "Create a blocking Question (last resort only) when stuck on hard informational ambiguity on another Issue. Performs structured dump + pause status on the original; returns the new Question #. Agent must have exhausted other tools/reasoning first, then pause work. Follow quiet comment rules for any additional updates.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "original_issue_number": {"type": "integer", "description": "The Issue (any type) that is blocked."},
                                        "blockage_point": {"type": "string", "description": "Exact point where safe progress stopped."},
                                        "missing_info": {"type": "string", "description": "What information is missing or ambiguous."},
                                        "suggested_questions": {"type": "array", "items": {"type": "string"}, "description": "Specific questions to ask the human (recommended)."},
                                        "partial_work": {"type": "string", "description": "What the agent has done/understood so far (to avoid loss)."},
                                        "extra_context": {"type": "string", "description": "Any additional artifacts or context."},
                                        "repo": {"type": "string", "description": "owner/name. Optional."},
                                    },
                                    "required": ["original_issue_number", "blockage_point", "missing_info"],
                                },
                            },
                            {
                                "name": "plate_release_status",
                                "description": "Return the current PLATE release status: release branch existence, open Release issues, active Next Release visibility, linked/on-hold Epics, track summary, pending unreleased fragments, and extension release checks.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "repo": {
                                            "type": "string",
                                            "description": "owner/name. Optional if running inside repo clone.",
                                        },
                                        "releases_dir": {
                                            "type": "string",
                                            "description": "Path to the releases directory. Defaults to .agentic/releases.",
                                        },
                                    },
                                },
                            },
                            {
                                "name": "plate_release_cleanup_branches",
                                "description": "Find dead remote branches (merged into base and no open PR) and optionally delete them as a fallback cleanup tool.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "repo": {
                                            "type": "string",
                                            "description": "owner/name. Optional if running inside repo clone.",
                                        },
                                        "base_branch": {
                                            "type": "string",
                                            "description": "Base branch to compare merge state against. Defaults to repository default branch.",
                                        },
                                        "apply": {
                                            "type": "boolean",
                                            "description": "When true, delete candidate branches. Defaults to false (dry-run).",
                                        },
                                        "limit": {
                                            "type": "integer",
                                            "description": "Optional max number of candidate branches to process.",
                                        },
                                    },
                                },
                            },
                            {
                                "name": "plate_release_target_epic",
                                "description": "Validate an Epic against the active Next Release and return the manual issue-linking guidance required because GitHub does not expose a public API to create the issue-to-issue sidebar link directly.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "epic_number": {
                                            "type": "integer",
                                            "description": "Epic issue number to validate against the active Next Release.",
                                        },
                                        "repo": {
                                            "type": "string",
                                            "description": "owner/name. Optional if running inside repo clone.",
                                        },
                                    },
                                    "required": ["epic_number"],
                                },
                            },
                            {
                                "name": "plate_release_notes",
                                "description": "Return a structured diff of PLATE release notes between two versions, including migration steps. Use to understand what changed between your current PLATE version and the latest.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "from_version": {
                                            "type": "string",
                                            "description": "Start version (exclusive, e.g. '0.1.2'). Omit for all versions from beginning.",
                                        },
                                        "to_version": {
                                            "type": "string",
                                            "description": "End version (inclusive, e.g. '0.2.0'). Omit for latest.",
                                        },
                                        "releases_dir": {
                                            "type": "string",
                                            "description": "Path to the releases directory. Defaults to .agentic/releases.",
                                        },
                                    },
                                },
                            },
                            {
                                "name": "plate_costs",
                                "description": "Harvest USAGE REPORT blocks from closed issues (per AGENTS.md), aggregate tokens/cost/duration for observability (Epic #265). Set dashboard=true for cost+risk dashboard with budgets, burn rate, drift signals, ranked feed items (#653/#634).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "repo": {
                                            "type": "string",
                                            "description": "owner/name. Optional if running inside repo clone.",
                                        },
                                        "epic_label": {
                                            "type": "string",
                                            "description": "Optional 'Epic: foo' label to scope aggregation.",
                                        },
                                        "dashboard": {
                                            "type": "boolean",
                                            "description": "When true, return cost+risk dashboard (#653/#634) instead of raw aggregate.",
                                        },
                                    },
                                    "required": [],
                                },
                            },
                            {
                                "name": "plate_autonomy_status",
                                "description": "Return AutonomyStatus (risk_tolerance, budget remaining, autopilot_score, due procedures, human checkpoints) for Epic #470 engine. Integrates health/costs/config.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "repo": {"type": "string", "description": "owner/name. Optional."},
                                    },
                                },
                            },
                            {
                                "name": "plate_pm_status",
                                "description": "Project Manager orchestrator status: budget, team size, open assignments/checkpoints (#660).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {"repo": {"type": "string"}},
                                },
                            },
                            {
                                "name": "plate_pm_team",
                                "description": "List pre-defined PM sub-agent personas (dev/design/research/release) (#660).",
                                "inputSchema": {"type": "object", "properties": {}},
                            },
                            {
                                "name": "plate_pm_assign",
                                "description": "Budget-aware assignment of one work item to a persona (#660).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "repo": {"type": "string"},
                                        "item": {"type": "object"},
                                    },
                                    "required": ["item"],
                                },
                            },
                            {
                                "name": "plate_pm_run_cycle",
                                "description": "Run one PM orchestration cycle: collect work, assign personas, respect budget/checkpoints (#660). Default dry_run=true.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "repo": {"type": "string"},
                                        "dry_run": {"type": "boolean"},
                                        "max_assignments": {"type": "integer"},
                                    },
                                },
                            },
                            {
                                "name": "plate_pm_run_loop",
                                "description": "Multi-cycle PM orchestrator loop with stop on checkpoints/budget/idle (#660). Default dry_run=true.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "repo": {"type": "string"},
                                        "dry_run": {"type": "boolean"},
                                        "max_cycles": {"type": "integer"},
                                        "max_assignments": {"type": "integer"},
                                    },
                                },
                            },
                            {
                                "name": "plate_pm_queue",
                                "description": "List durable PM assignment queue (.agentic/pm/queue.json) with ask_user_question payloads (#660).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "repo": {"type": "string"},
                                        "status": {
                                            "type": "string",
                                            "description": "proposed|delegated|blocked|done|cancelled|all",
                                        },
                                        "limit": {"type": "integer"},
                                    },
                                },
                            },
                            {
                                "name": "plate_pm_complete",
                                "description": "Mark a PM assignment done/cancelled and persist queue (#660).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "repo": {"type": "string"},
                                        "assignment_id": {"type": "string"},
                                        "status": {"type": "string"},
                                        "note": {"type": "string"},
                                    },
                                    "required": ["assignment_id"],
                                },
                            },
                            {
                                "name": "plate_ledger_record",
                                "description": "Append an inspectable PLATE-DECISION provenance entry for an autonomous action (#647). Durable under .agentic/ledger/.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "action_kind": {"type": "string"},
                                        "decision": {"type": "string", "description": "proceed|throttle|pause|warn|skip|approve|reject|..."},
                                        "reason": {"type": "string"},
                                        "sources": {"type": "array", "items": {"type": "string"}},
                                        "cost_estimate_tokens": {"type": "integer"},
                                        "risk_tolerance": {"type": "string"},
                                        "impact": {"type": "string"},
                                        "related_issue": {"type": "integer"},
                                        "related_pr": {"type": "integer"},
                                        "shadow_id": {"type": "string"},
                                        "checkpoint_id": {"type": "string"},
                                        "artifact_links": {"type": "array", "items": {"type": "string"}},
                                        "actor": {"type": "string"},
                                        "session": {"type": "string"},
                                        "metadata": {"type": "object"},
                                    },
                                    "required": ["action_kind", "decision", "reason"],
                                },
                            },
                            {
                                "name": "plate_ledger_list",
                                "description": "List recent decision ledger entries (#647), optional filters.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "action_kind": {"type": "string"},
                                        "decision": {"type": "string"},
                                        "related_issue": {"type": "integer"},
                                        "limit": {"type": "integer"},
                                    },
                                },
                            },
                            {
                                "name": "plate_ledger_query",
                                "description": "Substring search over decision ledger reason/sources/metadata (#647).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "query": {"type": "string"},
                                        "limit": {"type": "integer"},
                                    },
                                    "required": ["query"],
                                },
                            },
                            {
                                "name": "plate_ledger_get",
                                "description": "Get one decision ledger entry by id (#647).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "decision_id": {"type": "string"},
                                    },
                                    "required": ["decision_id"],
                                },
                            },
                            {
                                "name": "plate_ledger_summary",
                                "description": "Compact decision ledger summary counts (#647).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "limit": {"type": "integer"},
                                    },
                                },
                            },
                            {
                                "name": "plate_autonomy_run_cycle",
                                "description": "Run one AutonomyEngine cycle (introspect, enforce_budget, decide_next, execute/delegate). Supports dry_run and max_steps. For scheduled loops per #470.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "repo": {"type": "string", "description": "owner/name. Optional."},
                                        "dry_run": {"type": "boolean", "description": "Default false."},
                                        "max_steps": {"type": "integer", "description": "Cap actions this cycle."},
                                    },
                                },
                            },
                            {
                                "name": "plate_autonomy_list_procedures",
                                "description": "List loaded procedures (from .agentic/procedures/*.json + built-ins), filtered by current risk_tolerance.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "repo": {"type": "string", "description": "owner/name. Optional."},
                                    },
                                },
                            },
                            {
                                "name": "plate_autonomy_run_procedure",
                                "description": "Run a specific procedure by id (risk and budget checked). Supports dry_run. High-risk procedures may return shadow_required (#645) unless approved after plate_autonomy_simulate or an approved #648 checkpoint_id.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "repo": {"type": "string", "description": "owner/name. Optional."},
                                        "proc_id": {"type": "string", "description": "Procedure id e.g. nightly-drift-detection"},
                                        "dry_run": {"type": "boolean", "description": "Default false."},
                                        "shadow_ack": {"type": "string", "description": "shadow_id from plate_autonomy_simulate (#645)."},
                                        "approved": {"type": "boolean", "description": "Explicit human approval after shadow preview (#645)."},
                                        "checkpoint_id": {"type": "string", "description": "Approved #648 checkpoint id; supplies approval (+ shadow_id when present)."},
                                    },
                                    "required": ["proc_id"],
                                },
                            },
                            {
                                "name": "plate_autonomy_simulate",
                                "description": "Shadow/simulate a high-impact autonomous action without side effects (#645). Returns impact, cost/duration estimates, predicted side effects, gate preview, requires_approval, and shadow_id for later approval + execute.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "repo": {"type": "string", "description": "owner/name. Optional."},
                                        "action_kind": {
                                            "type": "string",
                                            "description": "Action to simulate e.g. release_cut, deploy, auto_merge, run_procedure, plan_epic.",
                                        },
                                        "scope": {
                                            "type": "object",
                                            "description": "Optional context (version, pr_number, risk_level, etc.).",
                                        },
                                    },
                                    "required": ["action_kind"],
                                },
                            },
                            {
                                "name": "plate_checkpoint_create",
                                "description": "Create a unified human checkpoint/approval request (#648). Durable under .agentic/checkpoints/; returns marker for GitHub comments. Can auto-approve low impact at medium+ risk_tolerance.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "repo": {"type": "string", "description": "owner/name. Optional."},
                                        "title": {"type": "string", "description": "Short checkpoint title for the feed."},
                                        "reason": {"type": "string", "description": "Why human judgment is required."},
                                        "impact": {"type": "string", "description": "low|medium|high|critical"},
                                        "action_kind": {"type": "string", "description": "Gated action e.g. release_cut, deploy, design_approve."},
                                        "scope": {"type": "object", "description": "Optional context payload."},
                                        "shadow_id": {"type": "string", "description": "Optional #645 shadow_id to attach."},
                                        "related_issue": {"type": "integer"},
                                        "related_pr": {"type": "integer"},
                                        "created_by": {"type": "string"},
                                    },
                                    "required": ["title", "reason"],
                                },
                            },
                            {
                                "name": "plate_checkpoint_decide",
                                "description": "Record approve|revise|reject|cancel on a checkpoint (#648). Clears pause_autonomy when decided.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "checkpoint_id": {"type": "string"},
                                        "decision": {"type": "string", "description": "approve|revise|reject|cancel"},
                                        "decided_by": {"type": "string"},
                                        "note": {"type": "string"},
                                    },
                                    "required": ["checkpoint_id", "decision"],
                                },
                            },
                            {
                                "name": "plate_checkpoint_list",
                                "description": "List checkpoints (#648). Default status=pending; open_only=true returns pausing ones.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "status": {"type": "string", "description": "pending|approved|rejected|auto_approved|all"},
                                        "open_only": {"type": "boolean"},
                                        "limit": {"type": "integer"},
                                    },
                                },
                            },
                            {
                                "name": "plate_checkpoint_get",
                                "description": "Get one checkpoint by id (#648).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "checkpoint_id": {"type": "string"},
                                    },
                                    "required": ["checkpoint_id"],
                                },
                            },
                            {
                                "name": "plate_migrate_plan",
                                "description": "Generate dry-run migration plan for template-to-plate cutover using current inventory and .plate state.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "repo": {"type": "string", "description": "owner/name. Optional."},
                                    },
                                },
                            },
                            {
                                "name": "plate_migrate_apply",
                                "description": "Apply migration steps (with checkpoint/rollback support). Use after reviewing plan.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "repo": {"type": "string", "description": "owner/name. Optional."},
                                        "dry_run": {"type": "boolean", "description": "Simulate only (default true for safety)."},
                                    },
                                },
                            },
                            {
                                "name": "plate_perform_information_audit",
                                "description": "Perform an Information Audit (Epic #218). Scans the Wiki Goals page + code/issues/PRs/discussions to surface Informational Goals and propose well-formed Question issues (per model in #220 and 10-rule contract in #223). Supports dry_run, scope, agent_type (general/marketing/engineering), max_questions, and include_defaults. Output feeds Curiosity/Q&A and Contemplation. v1 uses Goals signals + heuristics; full open-ended + refinement in follow-ups for #221.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "repo": {"type": "string", "description": "owner/name. Optional."},
                                        "scope": {"type": "string", "description": "repo | epic:<n> | label:<name> | surface:... (default: repo)"},
                                        "agent_type": {"type": "string", "description": "general | marketing | engineering (default: general) for specialized scoping/heuristics"},
                                        "max_questions": {"type": "integer", "description": "Cap on proposals (default 5)", "default": 5},
                                        "dry_run": {"type": "boolean", "description": "Propose only; do not create Issues (default false)", "default": False},
                                        "include_defaults": {"type": "boolean", "description": "Include platform + extension default informational goals (default true)", "default": True},
                                    },
                                },
                            },
                            # Discussions MCP surface (Feature #329). plate_* naming for consistency with other github/process tools.
                            # Supports Ideas category use cases, inter-agent comms, logs (Ideas #287, #292, #293; enables #282 orchestrator vision).
                            {
                                "name": "plate_list_discussions",
                                "description": "List discussions (filter by category e.g. 'ideas', state 'open'). Returns normalized records with number/title/url/body_preview.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "repo": {"type": "string", "description": "owner/name. Optional if inside clone."},
                                        "category": {"type": "string", "description": "Filter by category slug or name (e.g. 'ideas')."},
                                        "state": {"type": "string", "description": "open or closed (client filtered for reliability)."},
                                        "per_page": {"type": "integer", "description": "Max results (default 30)."},
                                        "page": {"type": "integer", "description": "Page (default 1)."},
                                    },
                                },
                            },
                            {
                                "name": "plate_get_discussion",
                                "description": "Get full discussion by number (includes body, category, etc.).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "repo": {"type": "string", "description": "owner/name. Optional."},
                                        "number": {"type": "integer", "description": "Discussion number."},
                                    },
                                    "required": ["number"],
                                },
                            },
                            {
                                "name": "plate_list_discussion_comments",
                                "description": "List comments on a discussion.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "repo": {"type": "string", "description": "owner/name. Optional."},
                                        "number": {"type": "integer", "description": "Discussion number."},
                                        "per_page": {"type": "integer", "description": "Max comments (default 30)."},
                                    },
                                    "required": ["number"],
                                },
                            },
                            {
                                "name": "plate_add_discussion_comment",
                                "description": "Add a comment to an existing discussion.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "repo": {"type": "string", "description": "owner/name. Optional."},
                                        "number": {"type": "integer", "description": "Discussion number."},
                                        "body": {"type": "string", "description": "Comment markdown content."},
                                    },
                                    "required": ["number", "body"],
                                },
                            },
                            {
                                "name": "plate_create_discussion",
                                "description": "Create a new discussion. Provide category_slug (e.g. 'ideas') or category_id (node ID).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "repo": {"type": "string", "description": "owner/name. Optional."},
                                        "category_slug": {"type": "string", "description": "Category slug or name (resolved via list)."},
                                        "category_id": {"type": "string", "description": "Direct category node ID (from GraphQL)."},
                                        "title": {"type": "string", "description": "Discussion title."},
                                        "body": {"type": "string", "description": "Discussion body (markdown)."},
                                    },
                                    "required": ["title", "body"],
                                },
                            },
                            {
                                "name": "plate_list_discussion_categories",
                                "description": "List available discussion categories (id, name, slug, description) for the repo.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "repo": {"type": "string", "description": "owner/name. Optional."},
                                    },
                                },
                            },
                            {
                                "name": "plate_list_open_ideas",
                                "description": "Convenience: list open discussions in the 'ideas' category (common for process/idea capture).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "repo": {"type": "string", "description": "owner/name. Optional."},
                                    },
                                },
                            },
                        ]
                    },
                }
            )
        elif method == "tools/call":
            _handle_tools_call(req_id, req.get("params", {}) or {})
        elif method == "notifications/initialized":
            continue
        elif req_id is None:
            continue
        else:
            _write(
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Unknown method: {method}"},
                }
            )


if __name__ == "__main__":
    run()
