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
from .autonomy import get_autonomy_status, get_budget_snapshot, run_autonomy_cycle
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
    decide_pending_plan,
    get_planning_script,
    list_pending_plans,
    planning_feed_items,
    start_planning_session,
)
from .epic_release_planning import (
    apply_er_answer,
    build_er_plan_from_session,
    decide_er_plan,
    er_planning_feed_items,
    get_er_script,
    start_er_session,
)
from .design_research_approval import (
    decide_proposal,
    get_proposal,
    get_proposal_history,
    list_actionable_proposals,
    list_authoritative,
    list_proposals,
    propose_artifact,
    resubmit_proposal,
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
from .fleet import (
    allocate_fleet_budget,
    complete_handoff,
    create_handoff,
    fleet_status,
    handoff_feed_items,
    list_fleet_roles,
    list_handoffs,
    plan_fleet_from_intent,
    update_handoff,
)
from .monitoring import (
    decide_proposal,
    list_proposals,
    monitor_market_signals,
    monitoring_feed_items,
    review_discussions,
    run_discussion_review_procedure,
    run_market_monitor_procedure,
)
from .stubs import (
    author_and_create,
    author_stub,
    create_stub_issue,
    get_stub,
    list_stubs,
    refine_stub,
    stubs_feed_items,
)
from .bug_loop import (
    advance_bug_loop,
    bug_loop_feed_items,
    cancel_bug_loop,
    get_bug_loop,
    list_bug_loops,
    run_bug_loop_tick,
    start_bug_loop,
    update_bug_loop,
)
from .feature_loop import (
    advance_feature_loop,
    cancel_feature_loop,
    estimate_feature_cost,
    feature_loop_feed_items,
    get_feature_loop,
    list_feature_loops,
    run_feature_loop_tick,
    start_feature_loop,
    update_feature_loop,
)
from .design_validation import (
    build_failing_test_scaffold,
    contract_feed_items,
    decide_contract,
    get_contract,
    list_contracts,
    propose_contract,
    update_contract,
    validate_contract_readiness,
)
from .release_media import (
    build_media_manifest,
    collect_release_media,
    decide_media_item,
    media_feed_items,
    render_media_markdown,
    validate_media_paths,
)
from .release import collect_fragments as collect_release_fragments
from .feature_media import (
    attach_to_fragment_file,
    decide_feature_media,
    feature_media_feed_items,
    get_feature_media,
    list_feature_media,
    plan_feature_media,
    register_capture,
    skip_feature_media,
)
from .packaging import (
    build_package,
    decide_package_publish,
    get_package,
    list_packages,
    packaging_feed_items,
    plan_marketplace_package_op,
    render_package_markdown,
)
from .hybrid import (
    detect_project_kind,
    feature_validation_plan,
    get_kind_contract,
    hybrid_feed_items,
    list_artifact_types,
    list_project_kinds,
    list_validation_strategies,
    load_project_profile,
    planning_template_for_kind,
    set_project_kind,
)
from .scheduled_ops import (
    complete_op_run,
    list_op_runs,
    list_ops,
    plan_op,
    run_scheduled_op,
    scheduled_ops_status,
    ops_feed_items,
)
from .tasks import close_task_with_signal, create_task, detect_and_create_tasks
from .collab import (
    analyze_pr_authorship,
    branch_etiquette_check,
    claim_ownership,
    collab_policy_check,
    collab_status_for_issue,
    concurrent_edit_risk,
    get_driver,
    list_ownership_claims,
    ownership_feed_items,
    release_ownership,
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
        elif name == "plate_planning_decide":
            payload = decide_pending_plan(
                str(args.get("plan_id") or args.get("id") or ""),
                str(args.get("decision") or "approve"),
                note=str(args.get("note") or ""),
                decided_by=str(args.get("decided_by") or args.get("by") or "mcp"),
            )
        elif name == "plate_planning_list_pending":
            if args.get("feed"):
                payload = {"feed": planning_feed_items(limit=int(args.get("limit") or 20))}
            else:
                payload = {
                    "pending": list_pending_plans(limit=int(args.get("limit") or 20))
                }
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
        elif name == "plate_er_planning_decide":
            payload = decide_er_plan(
                str(args.get("plan_id") or args.get("id") or ""),
                str(args.get("decision") or "approve"),
                note=str(args.get("note") or ""),
                decided_by=str(args.get("decided_by") or args.get("by") or "mcp"),
            )
        elif name == "plate_er_planning_list_pending":
            payload = {
                "items": er_planning_feed_items(limit=int(args.get("limit") or 20))
            }
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
                open_checkpoint=bool(args.get("open_checkpoint") or False),
            )
        elif name == "plate_artifact_resubmit":
            payload = resubmit_proposal(
                str(args.get("proposal_id") or args.get("id") or ""),
                summary=args.get("summary"),
                content_path=args.get("content_path"),
                content_excerpt=args.get("content_excerpt"),
                media_links=list(args.get("media_links") or []) if args.get("media_links") is not None else None,
                title=args.get("title"),
                actor=str(args.get("actor") or "agent"),
            )
        elif name == "plate_artifact_history":
            payload = {
                "history": get_proposal_history(
                    str(args.get("proposal_id") or args.get("id") or ""),
                    limit=int(args.get("limit") or 50),
                )
            }
        elif name == "plate_artifact_list":
            if args.get("authoritative"):
                payload = {"proposals": list_authoritative(kind=args.get("kind"))}
            elif args.get("actionable") or (args.get("status") == "actionable"):
                payload = {
                    "proposals": list_actionable_proposals(
                        kind=args.get("kind"),
                        limit=int(args.get("limit") or 50),
                    )
                }
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
        elif name == "plate_release_repair":
            from .release import repair_release_standing_state

            payload = repair_release_standing_state(
                repo=args.get("repo"),
                dry_run=not bool(args.get("apply", False)),
                apply=bool(args.get("apply", False)),
            )
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
        elif name == "plate_autonomy_budget":
            est = args.get("estimated_tokens") or args.get("estimate_tokens")
            payload = get_budget_snapshot(
                args.get("repo"),
                estimated_tokens=int(est) if est is not None else None,
            )
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
                dispatch_fleet=bool(args.get("dispatch_fleet", True)),
                dispatch_loops=bool(args.get("dispatch_loops", True)),
                tick_loops=bool(args.get("tick_loops", True)),
                fetch_loop_gates=bool(args.get("fetch_loop_gates") or False),
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
        elif name == "plate_fleet_status":
            payload = fleet_status(
                budget_remaining=args.get("budget_tokens") or args.get("budget_remaining"),
                risk_tolerance=str(args.get("risk_tolerance") or args.get("risk") or "medium"),
            )
        elif name == "plate_fleet_roles":
            payload = {"roles": list_fleet_roles()}
        elif name == "plate_fleet_handoff":
            payload = create_handoff(
                from_agent=str(args.get("from_agent") or "orchestrator"),
                to_agent=str(args.get("to_agent") or ""),
                task=str(args.get("task") or ""),
                context=args.get("context") if isinstance(args.get("context"), dict) else {},
                artifacts=list(args.get("artifacts") or []),
                constraints=list(args.get("constraints") or []),
                budget_tokens=args.get("budget_tokens"),
                risk=str(args.get("risk") or "medium"),
                related_issue=args.get("related_issue"),
                related_pr=args.get("related_pr"),
                parent_handoff_id=args.get("parent_handoff_id"),
                requires_human=bool(args.get("requires_human", False)),
            )
        elif name == "plate_fleet_update":
            payload = update_handoff(
                str(args.get("handoff_id") or args.get("id") or ""),
                status=args.get("status"),
                notes=args.get("notes") or args.get("note"),
                artifacts=list(args.get("artifacts") or []) or None,
                context_patch=args.get("context") if isinstance(args.get("context"), dict) else None,
            )
        elif name == "plate_fleet_complete":
            payload = complete_handoff(
                str(args.get("handoff_id") or args.get("id") or ""),
                notes=str(args.get("notes") or args.get("note") or ""),
                artifacts=list(args.get("artifacts") or []) or None,
            )
        elif name == "plate_fleet_list":
            payload = {
                "handoffs": list_handoffs(
                    status=str(args.get("status") or "active"),
                    to_agent=args.get("to_agent"),
                    from_agent=args.get("from_agent"),
                    limit=int(args.get("limit") or 50),
                )
            }
        elif name == "plate_fleet_allocate":
            roles = args.get("active_roles") or args.get("roles")
            if isinstance(roles, str):
                roles = [x.strip() for x in roles.split(",") if x.strip()]
            payload = allocate_fleet_budget(
                int(args.get("budget_tokens") or args.get("total_tokens") or 20000),
                active_roles=list(roles) if roles else None,
                risk_tolerance=str(args.get("risk_tolerance") or args.get("risk") or "medium"),
            )
        elif name == "plate_fleet_plan":
            payload = plan_fleet_from_intent(
                str(args.get("intent") or args.get("task") or ""),
                budget_tokens=int(args.get("budget_tokens") or 20000),
                risk_tolerance=str(args.get("risk_tolerance") or args.get("risk") or "medium"),
                related_issue=args.get("related_issue"),
                create=bool(args.get("create") or args.get("apply") or False),
            )
        elif name == "plate_fleet_feed":
            payload = {"items": handoff_feed_items(limit=int(args.get("limit") or 10))}
        elif name == "plate_monitor_discussions":
            dry = bool(args.get("dry_run", True))
            discussions = args.get("discussions")
            if isinstance(discussions, str):
                try:
                    discussions = json.loads(discussions)
                except Exception:
                    discussions = None
            if dry:
                payload = run_discussion_review_procedure(
                    repo=args.get("repo"),
                    discussions=list(discussions) if discussions else None,
                    dry_run=True,
                    fetch_live=False,
                )
            else:
                payload = review_discussions(
                    list(discussions) if discussions else None,
                    repo=args.get("repo"),
                    persist=bool(args.get("persist", True)),
                    fetch_live=bool(args.get("fetch_live", False)),
                    min_score=float(args.get("min_score") or 30),
                    limit=int(args.get("limit") or 10),
                )
        elif name == "plate_monitor_market":
            signals = args.get("signals") or []
            if isinstance(signals, str):
                try:
                    signals = json.loads(signals)
                except Exception:
                    signals = [{"title": signals}]
            dry = bool(args.get("dry_run", True))
            if dry:
                payload = run_market_monitor_procedure(signals=list(signals), dry_run=True)
            else:
                payload = monitor_market_signals(
                    list(signals),
                    persist=bool(args.get("persist", True)),
                    min_score=float(args.get("min_score") or 40),
                    limit=int(args.get("limit") or 10),
                )
        elif name == "plate_monitor_list":
            payload = {
                "proposals": list_proposals(
                    status=str(args.get("status") or "pending"),
                    source=args.get("source"),
                    limit=int(args.get("limit") or 50),
                )
            }
        elif name == "plate_monitor_decide":
            payload = decide_proposal(
                str(args.get("proposal_id") or args.get("id") or ""),
                str(args.get("decision") or "approve"),
                created_issue=args.get("created_issue"),
            )
        elif name == "plate_monitor_feed":
            payload = {"items": monitoring_feed_items(limit=int(args.get("limit") or 10))}
        elif name == "plate_stub_author":
            payload = author_stub(
                str(args.get("intent") or args.get("task") or ""),
                issue_type=args.get("issue_type") or args.get("type"),
                title=args.get("title"),
                summary=args.get("summary"),
                acceptance_criteria=list(args.get("acceptance_criteria") or []) or None,
                parent_epic=args.get("parent_epic"),
                milestone=args.get("milestone"),
                related_links=list(args.get("related_links") or []) or None,
                source=str(args.get("source") or "qa"),
                labels=list(args.get("labels") or []) or None,
                persist=bool(args.get("persist", True)),
            )
        elif name == "plate_stub_refine":
            payload = refine_stub(
                str(args.get("draft_id") or args.get("id") or ""),
                answers=args.get("answers") if isinstance(args.get("answers"), dict) else None,
                add_acceptance=list(args.get("add_acceptance") or args.get("acceptance_criteria") or []) or None,
                summary_append=args.get("summary_append") or args.get("summary"),
                issue_type=args.get("issue_type") or args.get("type"),
                note=args.get("note"),
                mark_ready=bool(args.get("mark_ready") or args.get("ready") or False),
            )
        elif name == "plate_stub_create":
            payload = create_stub_issue(
                args.get("draft_id") or args.get("id"),
                repo=args.get("repo"),
                dry_run=bool(args.get("dry_run", True)),
            )
        elif name == "plate_stub_list":
            payload = {
                "drafts": list_stubs(
                    status=str(args.get("status") or "all"),
                    issue_type=args.get("issue_type") or args.get("type"),
                    limit=int(args.get("limit") or 50),
                )
            }
        elif name == "plate_stub_get":
            payload = {"draft": get_stub(str(args.get("draft_id") or args.get("id") or ""))}
        elif name == "plate_stub_author_create":
            payload = author_and_create(
                str(args.get("intent") or ""),
                issue_type=args.get("issue_type") or args.get("type"),
                title=args.get("title"),
                dry_run=bool(args.get("dry_run", True)),
                repo=args.get("repo"),
                summary=args.get("summary"),
                source=str(args.get("source") or "qa"),
                parent_epic=args.get("parent_epic"),
            )
        elif name == "plate_stub_feed":
            payload = {"items": stubs_feed_items(limit=int(args.get("limit") or 10))}
        elif name == "plate_bug_loop_start":
            labels = args.get("labels") or []
            if isinstance(labels, str):
                labels = [x.strip() for x in labels.split(",") if x.strip()]
            payload = start_bug_loop(
                bug_number=args.get("bug_number") or args.get("bug"),
                bug_title=str(args.get("bug_title") or args.get("title") or ""),
                risk=str(args.get("risk") or "medium"),
                labels=list(labels) if labels else None,
                paths=list(args.get("paths") or []) or None,
                risk_tolerance=str(args.get("risk_tolerance") or "medium"),
                pr_number=args.get("pr_number") or args.get("pr"),
                branch=args.get("branch"),
            )
        elif name == "plate_bug_loop_advance":
            payload = advance_bug_loop(
                str(args.get("run_id") or args.get("id") or ""),
                pr_number=args.get("pr_number") or args.get("pr"),
                branch=args.get("branch"),
                note=args.get("note"),
                force_skip_checkpoint=bool(args.get("force_skip_checkpoint") or False),
                gates=args.get("gates") if isinstance(args.get("gates"), dict) else None,
            )
        elif name == "plate_bug_loop_tick":
            payload = run_bug_loop_tick(
                str(args.get("run_id") or args.get("id") or ""),
                dry_run=bool(args.get("dry_run", True)),
                fetch_gates=bool(args.get("fetch_gates") or False),
                repo=args.get("repo"),
            )
        elif name == "plate_bug_loop_list":
            payload = {
                "runs": list_bug_loops(
                    status=str(args.get("status") or "active"),
                    limit=int(args.get("limit") or 50),
                )
            }
        elif name == "plate_bug_loop_get":
            payload = {"run": get_bug_loop(str(args.get("run_id") or args.get("id") or ""))}
        elif name == "plate_bug_loop_cancel":
            payload = cancel_bug_loop(
                str(args.get("run_id") or args.get("id") or ""),
                note=str(args.get("note") or ""),
            )
        elif name == "plate_bug_loop_update":
            payload = update_bug_loop(
                str(args.get("run_id") or args.get("id") or ""),
                stage=args.get("stage"),
                status=args.get("status"),
                pr_number=args.get("pr_number") or args.get("pr"),
                branch=args.get("branch"),
                note=args.get("note"),
                checkpoint_id=args.get("checkpoint_id"),
            )
        elif name == "plate_bug_loop_feed":
            payload = {"items": bug_loop_feed_items(limit=int(args.get("limit") or 10))}
        elif name == "plate_feature_loop_estimate":
            payload = estimate_feature_cost(
                size=str(args.get("size") or "medium"),
                needs_design_validation=bool(args.get("needs_design_validation") or args.get("design") or False),
                needs_media=bool(args.get("needs_media", True)),
                e2e=bool(args.get("e2e") or False),
            )
        elif name == "plate_feature_loop_start":
            labels = args.get("labels") or []
            if isinstance(labels, str):
                labels = [x.strip() for x in labels.split(",") if x.strip()]
            use_live = args.get("use_live_budget")
            if use_live is None:
                use_live = True
            payload = start_feature_loop(
                feature_number=args.get("feature_number") or args.get("feature"),
                feature_title=str(args.get("feature_title") or args.get("title") or ""),
                risk=str(args.get("risk") or "medium"),
                size=str(args.get("size") or "medium"),
                labels=list(labels) if labels else None,
                paths=list(args.get("paths") or []) or None,
                risk_tolerance=str(args.get("risk_tolerance") or "medium"),
                needs_design_validation=bool(args.get("needs_design_validation") or args.get("design") or False),
                needs_media_approval=bool(args.get("needs_media_approval", True)),
                e2e=bool(args.get("e2e") or False),
                pr_number=args.get("pr_number") or args.get("pr"),
                branch=args.get("branch"),
                budget_remaining=args.get("budget_remaining"),
                use_live_budget=bool(use_live),
            )
        elif name == "plate_feature_loop_advance":
            payload = advance_feature_loop(
                str(args.get("run_id") or args.get("id") or ""),
                pr_number=args.get("pr_number") or args.get("pr"),
                branch=args.get("branch"),
                note=args.get("note"),
                force_skip_checkpoint=bool(args.get("force_skip_checkpoint") or False),
                skip_media=bool(args.get("skip_media") or False),
                gates=args.get("gates") if isinstance(args.get("gates"), dict) else None,
            )
        elif name == "plate_feature_loop_tick":
            payload = run_feature_loop_tick(
                str(args.get("run_id") or args.get("id") or ""),
                dry_run=bool(args.get("dry_run", True)),
                fetch_gates=bool(args.get("fetch_gates") or False),
                repo=args.get("repo"),
            )
        elif name == "plate_feature_loop_list":
            payload = {
                "runs": list_feature_loops(
                    status=str(args.get("status") or "active"),
                    limit=int(args.get("limit") or 50),
                )
            }
        elif name == "plate_feature_loop_get":
            payload = {"run": get_feature_loop(str(args.get("run_id") or args.get("id") or ""))}
        elif name == "plate_feature_loop_cancel":
            payload = cancel_feature_loop(
                str(args.get("run_id") or args.get("id") or ""),
                note=str(args.get("note") or ""),
            )
        elif name == "plate_feature_loop_update":
            payload = update_feature_loop(
                str(args.get("run_id") or args.get("id") or ""),
                stage=args.get("stage"),
                status=args.get("status"),
                pr_number=args.get("pr_number") or args.get("pr"),
                branch=args.get("branch"),
                note=args.get("note"),
                checkpoint_id=args.get("checkpoint_id"),
                cost_estimate_tokens=args.get("cost_estimate_tokens"),
            )
        elif name == "plate_feature_loop_feed":
            payload = {"items": feature_loop_feed_items(limit=int(args.get("limit") or 10))}
        elif name == "plate_design_contract_propose":
            payload = propose_contract(
                feature_number=args.get("feature_number") or args.get("feature"),
                feature_title=str(args.get("feature_title") or args.get("title") or ""),
                visual_specs=list(args.get("visual_specs") or []) or None,
                interaction_criteria=list(args.get("interaction_criteria") or []) or None,
                a11y_criteria=list(args.get("a11y_criteria") or []) or None,
                artifact_paths=list(args.get("artifact_paths") or []) or None,
                has_playwright=bool(args.get("has_playwright") or False),
                submit_for_approval=bool(args.get("submit_for_approval", True)),
            )
        elif name == "plate_design_contract_list":
            payload = {
                "contracts": list_contracts(
                    status=str(args.get("status") or "all"),
                    feature_number=args.get("feature_number") or args.get("feature"),
                    limit=int(args.get("limit") or 50),
                )
            }
        elif name == "plate_design_contract_get":
            payload = {"contract": get_contract(str(args.get("contract_id") or args.get("id") or ""))}
        elif name == "plate_design_contract_decide":
            payload = decide_contract(
                str(args.get("contract_id") or args.get("id") or ""),
                str(args.get("decision") or "approve"),
                decided_by=str(args.get("decided_by") or "human"),
                note=args.get("note"),
            )
        elif name == "plate_design_contract_update":
            payload = update_contract(
                str(args.get("contract_id") or args.get("id") or ""),
                visual_specs=list(args.get("visual_specs") or []) or None,
                interaction_criteria=list(args.get("interaction_criteria") or []) or None,
                a11y_criteria=list(args.get("a11y_criteria") or []) or None,
                artifact_paths=list(args.get("artifact_paths") or []) or None,
                status=args.get("status"),
            )
        elif name == "plate_design_contract_validate":
            payload = validate_contract_readiness(
                args.get("contract_id") or args.get("id"),
            )
        elif name == "plate_design_contract_scaffold":
            c = get_contract(str(args.get("contract_id") or args.get("id") or ""))
            if not c:
                payload = {"ok": False, "error": "contract not found"}
            else:
                payload = build_failing_test_scaffold(
                    c, language=str(args.get("language") or "python")
                )
                payload["ok"] = True
        elif name == "plate_design_contract_feed":
            payload = {"items": contract_feed_items(limit=int(args.get("limit") or 10))}
        elif name == "plate_release_media_manifest":
            from pathlib import Path as _P

            rdir = _P(str(args.get("releases_dir") or ".agentic/releases"))
            frags = collect_release_fragments(rdir)
            payload = build_media_manifest(frags, version=args.get("version"))
        elif name == "plate_release_media_render":
            from pathlib import Path as _P

            rdir = _P(str(args.get("releases_dir") or ".agentic/releases"))
            media = collect_release_media(collect_release_fragments(rdir))
            payload = {
                "markdown": render_media_markdown(
                    media, only_approved=bool(args.get("only_approved") or False)
                ),
                "n": len(media),
            }
        elif name == "plate_release_media_feed":
            from pathlib import Path as _P

            rdir = _P(str(args.get("releases_dir") or ".agentic/releases"))
            media = collect_release_media(collect_release_fragments(rdir))
            payload = {"items": media_feed_items(media)}
        elif name == "plate_release_media_validate_paths":
            from pathlib import Path as _P

            rdir = _P(str(args.get("releases_dir") or ".agentic/releases"))
            media = collect_release_media(collect_release_fragments(rdir))
            payload = validate_media_paths(media, repo_root=_P("."))
        elif name == "plate_release_media_decide":
            from pathlib import Path as _P

            rdir = _P(str(args.get("releases_dir") or ".agentic/releases"))
            media = collect_release_media(collect_release_fragments(rdir))
            payload = decide_media_item(
                media,
                index=args.get("index"),
                path=args.get("path"),
                url=args.get("url"),
                decision=str(args.get("decision") or "approve"),
            )
        elif name == "plate_hybrid_list_kinds":
            payload = {"kinds": list_project_kinds()}
        elif name == "plate_hybrid_list_artifacts":
            payload = {"artifact_types": list_artifact_types()}
        elif name == "plate_hybrid_list_validation":
            payload = {
                "validation": list_validation_strategies(kind=args.get("kind"))
            }
        elif name == "plate_hybrid_detect":
            from pathlib import Path as _P

            payload = detect_project_kind(_P(str(args.get("repo_root") or ".")))
        elif name == "plate_hybrid_set_kind":
            from pathlib import Path as _P

            payload = set_project_kind(
                str(args.get("kind") or ""),
                base_dir=_P(str(args.get("base_dir") or ".agentic/hybrid")),
                note=str(args.get("note") or ""),
            )
        elif name == "plate_hybrid_profile":
            from pathlib import Path as _P

            payload = load_project_profile(
                base_dir=_P(str(args.get("base_dir") or ".agentic/hybrid")),
                repo_root=_P(str(args.get("repo_root") or ".")),
            )
        elif name == "plate_hybrid_contract":
            c = get_kind_contract(str(args.get("kind") or ""))
            payload = {"ok": c is not None, "contract": c}
        elif name == "plate_hybrid_planning_template":
            payload = planning_template_for_kind(str(args.get("kind") or "software"))
        elif name == "plate_hybrid_validation_plan":
            payload = feature_validation_plan(
                str(args.get("kind") or "software"),
                feature_title=str(args.get("feature_title") or args.get("title") or ""),
                artifact_types=args.get("artifact_types"),
            )
        elif name == "plate_hybrid_feed":
            from pathlib import Path as _P

            payload = {
                "items": hybrid_feed_items(
                    base_dir=_P(str(args.get("base_dir") or ".agentic/hybrid")),
                    repo_root=_P(str(args.get("repo_root") or ".")),
                    limit=int(args.get("limit") or 4),
                )
            }
        elif name == "plate_packaging_build":
            from pathlib import Path as _P

            rdir = _P(str(args.get("releases_dir") or ".agentic/releases"))
            bdir = _P(str(args.get("base_dir") or ".agentic/packaging"))
            frags = collect_release_fragments(rdir)
            payload = build_package(
                str(args.get("version") or "unreleased"),
                frags,
                base_dir=bdir,
                require_approved_media=bool(args.get("require_approved_media") or False),
                persist=not bool(args.get("no_persist") or False),
            )
        elif name == "plate_packaging_list":
            from pathlib import Path as _P

            bdir = _P(str(args.get("base_dir") or ".agentic/packaging"))
            payload = {
                "packages": list_packages(
                    base_dir=bdir,
                    status=str(args.get("status") or "all"),
                    limit=int(args.get("limit") or 20),
                )
            }
        elif name == "plate_packaging_get":
            from pathlib import Path as _P

            bdir = _P(str(args.get("base_dir") or ".agentic/packaging"))
            p = get_package(str(args.get("package_id") or args.get("id") or ""), base_dir=bdir)
            payload = {"package": p, "ok": p is not None}
        elif name == "plate_packaging_render":
            from pathlib import Path as _P

            bdir = _P(str(args.get("base_dir") or ".agentic/packaging"))
            pid = str(args.get("package_id") or args.get("id") or "")
            p = get_package(pid, base_dir=bdir) if pid else None
            if p is None and args.get("version"):
                rdir = _P(str(args.get("releases_dir") or ".agentic/releases"))
                built = build_package(
                    str(args.get("version")),
                    collect_release_fragments(rdir),
                    base_dir=bdir,
                    persist=False,
                )
                p = built.get("package")
            if not p:
                payload = {"ok": False, "error": "package not found"}
            else:
                payload = {
                    "ok": True,
                    "markdown": render_package_markdown(p),
                    "package_id": p.get("id"),
                }
        elif name == "plate_packaging_decide":
            from pathlib import Path as _P

            bdir = _P(str(args.get("base_dir") or ".agentic/packaging"))
            payload = decide_package_publish(
                str(args.get("package_id") or args.get("id") or ""),
                str(args.get("decision") or "approve"),
                decided_by=str(args.get("decided_by") or "human"),
                note=str(args.get("note") or ""),
                base_dir=bdir,
            )
        elif name == "plate_packaging_feed":
            from pathlib import Path as _P

            bdir = _P(str(args.get("base_dir") or ".agentic/packaging"))
            payload = {
                "items": packaging_feed_items(
                    base_dir=bdir, limit=int(args.get("limit") or 8)
                )
            }
        elif name == "plate_packaging_plan":
            from pathlib import Path as _P

            payload = plan_marketplace_package_op(
                args.get("version"),
                releases_dir=_P(str(args.get("releases_dir") or ".agentic/releases")),
            )
        elif name == "plate_feature_media_plan":
            payload = plan_feature_media(
                feature_number=args.get("feature_number") or args.get("feature"),
                feature_title=str(args.get("feature_title") or args.get("title") or ""),
                test_name=args.get("test_name"),
                caption=args.get("caption"),
                fragment_slug=args.get("fragment_slug"),
                quality=str(args.get("quality") or "medium"),
            )
        elif name == "plate_feature_media_register":
            payload = register_capture(
                str(args.get("record_id") or args.get("id") or ""),
                gif_path=args.get("gif_path"),
                video_path=args.get("video_path"),
                size_bytes=args.get("size_bytes"),
                quality=args.get("quality"),
                capture_result=args.get("capture_result")
                if isinstance(args.get("capture_result"), dict)
                else None,
                submit_for_approval=bool(args.get("submit_for_approval", True)),
            )
        elif name == "plate_feature_media_list":
            payload = {
                "records": list_feature_media(
                    status=str(args.get("status") or "all"),
                    feature_number=args.get("feature_number") or args.get("feature"),
                    limit=int(args.get("limit") or 50),
                )
            }
        elif name == "plate_feature_media_get":
            payload = {
                "record": get_feature_media(str(args.get("record_id") or args.get("id") or ""))
            }
        elif name == "plate_feature_media_decide":
            payload = decide_feature_media(
                str(args.get("record_id") or args.get("id") or ""),
                str(args.get("decision") or "approve"),
                decided_by=str(args.get("decided_by") or "human"),
                note=args.get("note"),
            )
        elif name == "plate_feature_media_skip":
            payload = skip_feature_media(
                str(args.get("record_id") or args.get("id") or ""),
                note=str(args.get("note") or ""),
            )
        elif name == "plate_feature_media_attach_fragment":
            payload = attach_to_fragment_file(
                str(args.get("record_id") or args.get("id") or ""),
                str(args.get("fragment_path") or args.get("fragment") or ""),
            )
        elif name == "plate_feature_media_feed":
            payload = {"items": feature_media_feed_items(limit=int(args.get("limit") or 10))}
        elif name == "plate_scheduled_ops_list":
            payload = {"ops": list_ops()}
        elif name == "plate_scheduled_ops_status":
            payload = scheduled_ops_status(
                risk_tolerance=str(args.get("risk_tolerance") or "medium")
            )
        elif name == "plate_scheduled_op_plan":
            payload = plan_op(
                str(args.get("op_id") or args.get("id") or ""),
                dry_run=bool(args.get("dry_run", True)),
            )
        elif name == "plate_scheduled_op_run":
            payload = run_scheduled_op(
                str(args.get("op_id") or args.get("id") or ""),
                dry_run=bool(args.get("dry_run", True)),
                risk_tolerance=str(args.get("risk_tolerance") or "medium"),
                approved=bool(args.get("approved") or False),
                checkpoint_id=args.get("checkpoint_id"),
                note=str(args.get("note") or ""),
            )
        elif name == "plate_scheduled_op_runs":
            payload = {
                "runs": list_op_runs(
                    op_id=args.get("op_id"),
                    status=str(args.get("status") or "all"),
                    limit=int(args.get("limit") or 50),
                )
            }
        elif name == "plate_scheduled_op_complete":
            payload = complete_op_run(
                str(args.get("run_id") or args.get("id") or ""),
                status=str(args.get("status") or "done"),
                note=str(args.get("note") or ""),
            )
        elif name == "plate_scheduled_ops_feed":
            payload = {
                "items": ops_feed_items(
                    risk_tolerance=str(args.get("risk_tolerance") or "medium"),
                    limit=int(args.get("limit") or 10),
                )
            }
        elif name == "plate_task_create":
            payload = create_task(
                str(args.get("title") or ""),
                human_action=str(args.get("human_action") or args.get("action") or ""),
                why_agent_cannot=str(args.get("why_agent_cannot") or args.get("why") or ""),
                context=str(args.get("context") or ""),
                instructions=str(args.get("instructions") or ""),
                done_signal=args.get("done_signal"),
                related_links=args.get("related_links") or args.get("related"),
                milestone=args.get("milestone"),
                epic_milestone_name=args.get("epic_milestone"),
                labels=list(args.get("labels") or []) if isinstance(args.get("labels"), list) else None,
                repo=args.get("repo"),
                dry_run=bool(args.get("dry_run", False)),
            )
        elif name == "plate_task_close":
            payload = close_task_with_signal(
                int(args.get("number") or args.get("issue_number") or 0),
                comment=str(args.get("comment") or args.get("note") or "Task complete."),
                repo=args.get("repo"),
                dry_run=bool(args.get("dry_run", False)),
            )
        elif name == "plate_task_detect":
            signals = args.get("signals")
            if isinstance(signals, str):
                signals = [signals]
            payload = detect_and_create_tasks(
                signals=list(signals) if isinstance(signals, list) else None,
                text=str(args.get("text") or args.get("signal") or "") or None,
                context=str(args.get("context") or ""),
                repo=args.get("repo"),
                dry_run=bool(args.get("dry_run", True)),
                create=bool(args.get("create", False)),
            )
        elif name == "plate_collab_check":
            labels = args.get("labels") or []
            if isinstance(labels, str):
                labels = [labels]
            auth = None
            if args.get("commits") or args.get("author_login"):
                auth = analyze_pr_authorship(
                    pr_number=args.get("pr_number"),
                    author_login=args.get("author_login"),
                    commits=list(args.get("commits") or []) if isinstance(args.get("commits"), list) else None,
                )
            paths = args.get("paths") or []
            if isinstance(paths, str):
                paths = [p.strip() for p in paths.split(",") if p.strip()]
            payload = collab_policy_check(
                str(args.get("action") or "delegate"),
                labels=list(labels),
                authorship=auth,
                paths=list(paths) if paths else None,
                branch=args.get("branch"),
                worktree_root=args.get("worktree_root"),
                repo_root=args.get("repo_root"),
            )
            payload["driver"] = get_driver(list(labels))
            if auth is not None:
                payload["authorship"] = auth.to_dict() if hasattr(auth, "to_dict") else auth
        elif name == "plate_collab_issue_status":
            issue = args.get("issue") or {}
            if isinstance(issue, str):
                issue = {"title": issue, "labels": args.get("labels") or []}
            if not issue.get("labels") and args.get("labels"):
                issue = dict(issue)
                issue["labels"] = args.get("labels")
            payload = collab_status_for_issue(issue if isinstance(issue, dict) else {})
        elif name == "plate_collab_ownership_claim":
            payload = claim_ownership(
                kind=str(args.get("kind") or "path"),
                target=str(args.get("target") or ""),
                owner=str(args.get("owner") or "human"),
                reason=str(args.get("reason") or ""),
                related_issue=args.get("related_issue"),
                actor=str(args.get("actor") or "human"),
            )
        elif name == "plate_collab_ownership_release":
            payload = release_ownership(
                args.get("claim_id") or args.get("id"),
                kind=args.get("kind"),
                target=args.get("target"),
            )
        elif name == "plate_collab_ownership_list":
            payload = {
                "claims": list_ownership_claims(
                    status=str(args.get("status") or "open"),
                    kind=args.get("kind"),
                    limit=int(args.get("limit") or 50),
                )
            }
        elif name == "plate_collab_etiquette":
            payload = branch_etiquette_check(
                args.get("branch"),
                worktree_root=args.get("worktree_root"),
                repo_root=args.get("repo_root"),
            )
        elif name == "plate_collab_concurrent":
            paths = args.get("paths") or []
            if isinstance(paths, str):
                paths = [p.strip() for p in paths.split(",") if p.strip()]
            payload = concurrent_edit_risk(list(paths))
        elif name == "plate_collab_ownership_feed":
            payload = {"items": ownership_feed_items(limit=int(args.get("limit") or 10))}
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
                                "name": "plate_planning_decide",
                                "description": "Approve/revise/reject a pending Q&A plan stub (#628/#630). Does not auto-create GitHub issues.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "plan_id": {"type": "string", "description": "Pending plan id"},
                                        "decision": {
                                            "type": "string",
                                            "description": "approve | revise | reject",
                                        },
                                        "note": {"type": "string"},
                                        "decided_by": {"type": "string"},
                                    },
                                    "required": ["plan_id", "decision"],
                                },
                            },
                            {
                                "name": "plate_planning_list_pending",
                                "description": "List pending plan stubs or planning feed items (pending + incomplete sessions).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "feed": {
                                            "type": "boolean",
                                            "description": "If true, return planning_feed_items shape",
                                        },
                                        "limit": {"type": "integer"},
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
                                "name": "plate_er_planning_decide",
                                "description": "Approve/revise/reject a pending epic/release plan (#640/#629). Does not create issues or cut releases.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "plan_id": {"type": "string"},
                                        "decision": {
                                            "type": "string",
                                            "description": "approve | revise | reject",
                                        },
                                        "note": {"type": "string"},
                                        "decided_by": {"type": "string"},
                                    },
                                    "required": ["plan_id", "decision"],
                                },
                            },
                            {
                                "name": "plate_er_planning_list_pending",
                                "description": "List pending epic/release plans and incomplete ER sessions for the feed.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "limit": {"type": "integer"},
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
                                        "open_checkpoint": {
                                            "type": "boolean",
                                            "description": "On revise, open #648 checkpoint if related_issue set",
                                        },
                                    },
                                    "required": ["proposal_id", "decision"],
                                },
                            },
                            {
                                "name": "plate_artifact_resubmit",
                                "description": "Resubmit a revised Design/Research proposal after content update (#632).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "proposal_id": {"type": "string"},
                                        "summary": {"type": "string"},
                                        "content_path": {"type": "string"},
                                        "content_excerpt": {"type": "string"},
                                        "title": {"type": "string"},
                                        "media_links": {"type": "array", "items": {"type": "string"}},
                                        "actor": {"type": "string"},
                                    },
                                    "required": ["proposal_id"],
                                },
                            },
                            {
                                "name": "plate_artifact_history",
                                "description": "Decision history for a Design/Research proposal (#632).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "proposal_id": {"type": "string"},
                                        "limit": {"type": "integer"},
                                    },
                                    "required": ["proposal_id"],
                                },
                            },
                            {
                                "name": "plate_artifact_list",
                                "description": "List pending/actionable/authoritative Design/Research approval proposals (#632).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "status": {
                                            "type": "string",
                                            "description": "pending|revised|approved|rejected|actionable|all",
                                        },
                                        "kind": {"type": "string"},
                                        "authoritative": {"type": "boolean"},
                                        "actionable": {
                                            "type": "boolean",
                                            "description": "If true, list pending+revised",
                                        },
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
                                "name": "plate_release_repair",
                                "description": "Init/repair standing release tracks (release-major/minor/patch + legacy release) and ensure exactly one Next Release issue (#320). Default dry-run; set apply=true to create missing artifacts.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "repo": {"type": "string"},
                                        "apply": {"type": "boolean"},
                                    },
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
                                "name": "plate_autonomy_budget",
                                "description": "Durable #634 budget snapshot: limits, spend.json counters, remaining tokens/USD, pressure, optional estimate would_pause/throttle. Use before long feature loops.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "repo": {"type": "string", "description": "owner/name. Optional."},
                                        "estimated_tokens": {
                                            "type": "integer",
                                            "description": "Optional estimate to project would_pause/throttle.",
                                        },
                                        "estimate_tokens": {
                                            "type": "integer",
                                            "description": "Alias for estimated_tokens.",
                                        },
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
                                "description": "Run one PM orchestration cycle: collect work, assign personas, respect budget/checkpoints; may dispatch fleet/loops and tick delegated #638/#639 loops (#660). Default dry_run=true.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "repo": {"type": "string"},
                                        "dry_run": {"type": "boolean"},
                                        "max_assignments": {"type": "integer"},
                                        "dispatch_fleet": {"type": "boolean"},
                                        "dispatch_loops": {"type": "boolean"},
                                        "tick_loops": {
                                            "type": "boolean",
                                            "description": "Sync loop stages and complete assignments when loops done (default true).",
                                        },
                                        "fetch_loop_gates": {
                                            "type": "boolean",
                                            "description": "When apply (dry_run=false), fetch PR gates on babysit ticks.",
                                        },
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
                                "name": "plate_fleet_status",
                                "description": "Multi-agent fleet status: roles, active handoffs, budget allocation (#644).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "budget_tokens": {"type": "integer"},
                                        "risk_tolerance": {"type": "string"},
                                    },
                                },
                            },
                            {
                                "name": "plate_fleet_roles",
                                "description": "List fleet agent roles (planner/implementer/reviewer/researcher/deployer/market) (#644).",
                                "inputSchema": {"type": "object", "properties": {}},
                            },
                            {
                                "name": "plate_fleet_handoff",
                                "description": "Create explicit agent→agent handoff packet with narrow context (#644).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "from_agent": {"type": "string"},
                                        "to_agent": {"type": "string"},
                                        "task": {"type": "string"},
                                        "context": {"type": "object"},
                                        "artifacts": {"type": "array", "items": {"type": "string"}},
                                        "constraints": {"type": "array", "items": {"type": "string"}},
                                        "budget_tokens": {"type": "integer"},
                                        "risk": {"type": "string"},
                                        "related_issue": {"type": "integer"},
                                        "related_pr": {"type": "integer"},
                                        "parent_handoff_id": {"type": "string"},
                                        "requires_human": {"type": "boolean"},
                                    },
                                    "required": ["to_agent", "task"],
                                },
                            },
                            {
                                "name": "plate_fleet_update",
                                "description": "Update handoff status (accepted|done|blocked|cancelled) (#644).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "handoff_id": {"type": "string"},
                                        "id": {"type": "string"},
                                        "status": {"type": "string"},
                                        "notes": {"type": "string"},
                                        "artifacts": {"type": "array", "items": {"type": "string"}},
                                        "context": {"type": "object"},
                                    },
                                },
                            },
                            {
                                "name": "plate_fleet_complete",
                                "description": "Mark a fleet handoff done (#644).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "handoff_id": {"type": "string"},
                                        "id": {"type": "string"},
                                        "notes": {"type": "string"},
                                        "artifacts": {"type": "array", "items": {"type": "string"}},
                                    },
                                    "required": ["handoff_id"],
                                },
                            },
                            {
                                "name": "plate_fleet_list",
                                "description": "List fleet handoffs (default active) (#644).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "status": {"type": "string"},
                                        "to_agent": {"type": "string"},
                                        "from_agent": {"type": "string"},
                                        "limit": {"type": "integer"},
                                    },
                                },
                            },
                            {
                                "name": "plate_fleet_allocate",
                                "description": "Allocate token budget across concurrent fleet agents (#644).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "budget_tokens": {"type": "integer"},
                                        "active_roles": {"type": "array", "items": {"type": "string"}},
                                        "risk_tolerance": {"type": "string"},
                                    },
                                },
                            },
                            {
                                "name": "plate_fleet_plan",
                                "description": "Plan multi-agent handoffs from high-level intent; optional create (#644).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "intent": {"type": "string"},
                                        "task": {"type": "string"},
                                        "budget_tokens": {"type": "integer"},
                                        "risk_tolerance": {"type": "string"},
                                        "related_issue": {"type": "integer"},
                                        "create": {"type": "boolean"},
                                        "apply": {"type": "boolean"},
                                    },
                                    "required": ["intent"],
                                },
                            },
                            {
                                "name": "plate_fleet_feed",
                                "description": "Feed presentation items for active fleet handoffs (#644).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {"limit": {"type": "integer"}},
                                },
                            },
                            {
                                "name": "plate_monitor_discussions",
                                "description": "Review Discussions/Ideas into ranked stub issue proposals (#642). dry_run default true.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "repo": {"type": "string"},
                                        "discussions": {"type": "array", "items": {"type": "object"}},
                                        "dry_run": {"type": "boolean"},
                                        "fetch_live": {"type": "boolean"},
                                        "persist": {"type": "boolean"},
                                        "min_score": {"type": "number"},
                                        "limit": {"type": "integer"},
                                    },
                                },
                            },
                            {
                                "name": "plate_monitor_market",
                                "description": "Synthesize host-injected market signals into Question proposals (#642). No outbound network.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "signals": {"type": "array", "items": {"type": "object"}},
                                        "dry_run": {"type": "boolean"},
                                        "persist": {"type": "boolean"},
                                        "min_score": {"type": "number"},
                                        "limit": {"type": "integer"},
                                    },
                                },
                            },
                            {
                                "name": "plate_monitor_list",
                                "description": "List monitoring proposals (default pending) (#642).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "status": {"type": "string"},
                                        "source": {"type": "string"},
                                        "limit": {"type": "integer"},
                                    },
                                },
                            },
                            {
                                "name": "plate_monitor_decide",
                                "description": "Approve/reject/created a monitoring proposal (#642).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "proposal_id": {"type": "string"},
                                        "id": {"type": "string"},
                                        "decision": {"type": "string"},
                                        "created_issue": {"type": "integer"},
                                    },
                                    "required": ["proposal_id", "decision"],
                                },
                            },
                            {
                                "name": "plate_monitor_feed",
                                "description": "Feed presentation for pending monitoring proposals (#642).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {"limit": {"type": "integer"}},
                                },
                            },
                            {
                                "name": "plate_stub_author",
                                "description": "Author a local stub Issue draft of any PLATE type from intent/Q&A (#637).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "intent": {"type": "string"},
                                        "task": {"type": "string"},
                                        "issue_type": {"type": "string"},
                                        "type": {"type": "string"},
                                        "title": {"type": "string"},
                                        "summary": {"type": "string"},
                                        "acceptance_criteria": {"type": "array", "items": {"type": "string"}},
                                        "parent_epic": {},
                                        "milestone": {},
                                        "related_links": {"type": "array", "items": {"type": "string"}},
                                        "source": {"type": "string"},
                                        "labels": {"type": "array", "items": {"type": "string"}},
                                        "persist": {"type": "boolean"},
                                    },
                                    "required": ["intent"],
                                },
                            },
                            {
                                "name": "plate_stub_refine",
                                "description": "Refine a stub draft with Q&A answers / AC / type changes (#637).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "draft_id": {"type": "string"},
                                        "id": {"type": "string"},
                                        "answers": {"type": "object"},
                                        "add_acceptance": {"type": "array", "items": {"type": "string"}},
                                        "summary_append": {"type": "string"},
                                        "issue_type": {"type": "string"},
                                        "note": {"type": "string"},
                                        "mark_ready": {"type": "boolean"},
                                    },
                                    "required": ["draft_id"],
                                },
                            },
                            {
                                "name": "plate_stub_create",
                                "description": "Create GitHub issue from stub draft (dry_run default true) (#637).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "draft_id": {"type": "string"},
                                        "id": {"type": "string"},
                                        "repo": {"type": "string"},
                                        "dry_run": {"type": "boolean"},
                                    },
                                },
                            },
                            {
                                "name": "plate_stub_list",
                                "description": "List local stub drafts (#637).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "status": {"type": "string"},
                                        "issue_type": {"type": "string"},
                                        "limit": {"type": "integer"},
                                    },
                                },
                            },
                            {
                                "name": "plate_stub_get",
                                "description": "Get one stub draft by id (#637).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "draft_id": {"type": "string"},
                                        "id": {"type": "string"},
                                    },
                                    "required": ["draft_id"],
                                },
                            },
                            {
                                "name": "plate_stub_author_create",
                                "description": "Author stub then dry-run/create GitHub issue in one call (#637).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "intent": {"type": "string"},
                                        "issue_type": {"type": "string"},
                                        "title": {"type": "string"},
                                        "summary": {"type": "string"},
                                        "repo": {"type": "string"},
                                        "dry_run": {"type": "boolean"},
                                        "source": {"type": "string"},
                                        "parent_epic": {},
                                    },
                                    "required": ["intent"],
                                },
                            },
                            {
                                "name": "plate_stub_feed",
                                "description": "Feed presentation for stub drafts awaiting create/refine (#637).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {"limit": {"type": "integer"}},
                                },
                            },
                            {
                                "name": "plate_bug_loop_start",
                                "description": "Start autonomous bug resolution loop run (#638): plan→TDD→PR→babysit→merge-eligible.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "bug_number": {"type": "integer"},
                                        "bug": {"type": "integer"},
                                        "bug_title": {"type": "string"},
                                        "title": {"type": "string"},
                                        "risk": {"type": "string"},
                                        "labels": {"type": "array", "items": {"type": "string"}},
                                        "paths": {"type": "array", "items": {"type": "string"}},
                                        "risk_tolerance": {"type": "string"},
                                        "pr_number": {"type": "integer"},
                                        "pr": {"type": "integer"},
                                        "branch": {"type": "string"},
                                    },
                                },
                            },
                            {
                                "name": "plate_bug_loop_advance",
                                "description": "Advance bug loop one stage; babysit stage honors optional merge gates (#638).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "run_id": {"type": "string"},
                                        "id": {"type": "string"},
                                        "pr_number": {"type": "integer"},
                                        "branch": {"type": "string"},
                                        "note": {"type": "string"},
                                        "force_skip_checkpoint": {"type": "boolean"},
                                        "gates": {"type": "object"},
                                    },
                                    "required": ["run_id"],
                                },
                            },
                            {
                                "name": "plate_bug_loop_tick",
                                "description": "One bug-loop tick: emit stage packet; optional gate fetch; auto-advance only if dry_run=false (#638).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "run_id": {"type": "string"},
                                        "dry_run": {"type": "boolean"},
                                        "fetch_gates": {"type": "boolean"},
                                        "repo": {"type": "string"},
                                    },
                                    "required": ["run_id"],
                                },
                            },
                            {
                                "name": "plate_bug_loop_list",
                                "description": "List bug resolution loop runs (#638).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "status": {"type": "string"},
                                        "limit": {"type": "integer"},
                                    },
                                },
                            },
                            {
                                "name": "plate_bug_loop_get",
                                "description": "Get one bug loop run (#638).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "run_id": {"type": "string"},
                                        "id": {"type": "string"},
                                    },
                                    "required": ["run_id"],
                                },
                            },
                            {
                                "name": "plate_bug_loop_cancel",
                                "description": "Cancel a bug loop run (#638).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "run_id": {"type": "string"},
                                        "note": {"type": "string"},
                                    },
                                    "required": ["run_id"],
                                },
                            },
                            {
                                "name": "plate_bug_loop_update",
                                "description": "Update bug loop fields (stage, pr, branch, checkpoint) (#638).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "run_id": {"type": "string"},
                                        "stage": {"type": "string"},
                                        "status": {"type": "string"},
                                        "pr_number": {"type": "integer"},
                                        "branch": {"type": "string"},
                                        "note": {"type": "string"},
                                        "checkpoint_id": {"type": "string"},
                                    },
                                    "required": ["run_id"],
                                },
                            },
                            {
                                "name": "plate_bug_loop_feed",
                                "description": "Feed presentation for active bug resolution loops (#638).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {"limit": {"type": "integer"}},
                                },
                            },
                            {
                                "name": "plate_feature_loop_estimate",
                                "description": "Upfront cost estimate for a Feature implementation loop (#639).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "size": {"type": "string"},
                                        "needs_design_validation": {"type": "boolean"},
                                        "design": {"type": "boolean"},
                                        "needs_media": {"type": "boolean"},
                                        "e2e": {"type": "boolean"},
                                    },
                                },
                            },
                            {
                                "name": "plate_feature_loop_start",
                                "description": "Start Feature loop: estimate→plan→TDD→docs→media→babysit→merge-eligible (#639).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "feature_number": {"type": "integer"},
                                        "feature": {"type": "integer"},
                                        "feature_title": {"type": "string"},
                                        "title": {"type": "string"},
                                        "risk": {"type": "string"},
                                        "size": {"type": "string"},
                                        "labels": {"type": "array", "items": {"type": "string"}},
                                        "paths": {"type": "array", "items": {"type": "string"}},
                                        "risk_tolerance": {"type": "string"},
                                        "needs_design_validation": {"type": "boolean"},
                                        "needs_media_approval": {"type": "boolean"},
                                        "e2e": {"type": "boolean"},
                                        "pr_number": {"type": "integer"},
                                        "branch": {"type": "string"},
                                        "budget_remaining": {"type": "integer"},
                                        "use_live_budget": {
                                            "type": "boolean",
                                            "description": "When true (default), hydrate remaining tokens from durable #634 snapshot if budget_remaining omitted.",
                                        },
                                    },
                                },
                            },
                            {
                                "name": "plate_feature_loop_advance",
                                "description": "Advance Feature loop one stage; babysit honors optional merge gates (#639).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "run_id": {"type": "string"},
                                        "pr_number": {"type": "integer"},
                                        "branch": {"type": "string"},
                                        "note": {"type": "string"},
                                        "force_skip_checkpoint": {"type": "boolean"},
                                        "skip_media": {"type": "boolean"},
                                        "gates": {"type": "object"},
                                    },
                                    "required": ["run_id"],
                                },
                            },
                            {
                                "name": "plate_feature_loop_tick",
                                "description": "One Feature-loop tick with optional gate fetch (#639).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "run_id": {"type": "string"},
                                        "dry_run": {"type": "boolean"},
                                        "fetch_gates": {"type": "boolean"},
                                        "repo": {"type": "string"},
                                    },
                                    "required": ["run_id"],
                                },
                            },
                            {
                                "name": "plate_feature_loop_list",
                                "description": "List Feature implementation loop runs (#639).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "status": {"type": "string"},
                                        "limit": {"type": "integer"},
                                    },
                                },
                            },
                            {
                                "name": "plate_feature_loop_get",
                                "description": "Get one Feature loop run (#639).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {"run_id": {"type": "string"}},
                                    "required": ["run_id"],
                                },
                            },
                            {
                                "name": "plate_feature_loop_cancel",
                                "description": "Cancel a Feature loop run (#639).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "run_id": {"type": "string"},
                                        "note": {"type": "string"},
                                    },
                                    "required": ["run_id"],
                                },
                            },
                            {
                                "name": "plate_feature_loop_update",
                                "description": "Update Feature loop fields (#639).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "run_id": {"type": "string"},
                                        "stage": {"type": "string"},
                                        "status": {"type": "string"},
                                        "pr_number": {"type": "integer"},
                                        "branch": {"type": "string"},
                                        "note": {"type": "string"},
                                        "checkpoint_id": {"type": "string"},
                                        "cost_estimate_tokens": {"type": "integer"},
                                    },
                                    "required": ["run_id"],
                                },
                            },
                            {
                                "name": "plate_feature_loop_feed",
                                "description": "Feed presentation for active Feature loops (#639).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {"limit": {"type": "integer"}},
                                },
                            },
                            {
                                "name": "plate_design_contract_propose",
                                "description": "Propose visual/interaction design contract for a Feature with failing-test scaffold (#646).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "feature_number": {"type": "integer"},
                                        "feature_title": {"type": "string"},
                                        "title": {"type": "string"},
                                        "visual_specs": {"type": "array", "items": {"type": "string"}},
                                        "interaction_criteria": {"type": "array", "items": {"type": "string"}},
                                        "a11y_criteria": {"type": "array", "items": {"type": "string"}},
                                        "artifact_paths": {"type": "array", "items": {"type": "string"}},
                                        "has_playwright": {"type": "boolean"},
                                        "submit_for_approval": {"type": "boolean"},
                                    },
                                },
                            },
                            {
                                "name": "plate_design_contract_list",
                                "description": "List design contracts (#646).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "status": {"type": "string"},
                                        "feature_number": {"type": "integer"},
                                        "limit": {"type": "integer"},
                                    },
                                },
                            },
                            {
                                "name": "plate_design_contract_get",
                                "description": "Get one design contract (#646).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {"contract_id": {"type": "string"}},
                                    "required": ["contract_id"],
                                },
                            },
                            {
                                "name": "plate_design_contract_decide",
                                "description": "Approve/reject/revise a design contract (#646).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "contract_id": {"type": "string"},
                                        "decision": {"type": "string"},
                                        "decided_by": {"type": "string"},
                                        "note": {"type": "string"},
                                    },
                                    "required": ["contract_id", "decision"],
                                },
                            },
                            {
                                "name": "plate_design_contract_update",
                                "description": "Update design contract criteria (#646).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "contract_id": {"type": "string"},
                                        "visual_specs": {"type": "array", "items": {"type": "string"}},
                                        "interaction_criteria": {"type": "array", "items": {"type": "string"}},
                                        "a11y_criteria": {"type": "array", "items": {"type": "string"}},
                                        "artifact_paths": {"type": "array", "items": {"type": "string"}},
                                        "status": {"type": "string"},
                                    },
                                    "required": ["contract_id"],
                                },
                            },
                            {
                                "name": "plate_design_contract_validate",
                                "description": "Check if design contract is ready for Feature implementation (#646).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {"contract_id": {"type": "string"}},
                                    "required": ["contract_id"],
                                },
                            },
                            {
                                "name": "plate_design_contract_scaffold",
                                "description": "Generate failing design-contract test scaffold (python|typescript) (#646).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "contract_id": {"type": "string"},
                                        "language": {"type": "string"},
                                    },
                                    "required": ["contract_id"],
                                },
                            },
                            {
                                "name": "plate_design_contract_feed",
                                "description": "Feed presentation for pending design contracts (#646).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {"limit": {"type": "integer"}},
                                },
                            },
                            {
                                "name": "plate_release_media_manifest",
                                "description": "Aggregate GIF/video media from unreleased fragments for release notes (#635).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "releases_dir": {"type": "string"},
                                        "version": {"type": "string"},
                                    },
                                },
                            },
                            {
                                "name": "plate_release_media_render",
                                "description": "Render release media markdown from fragments (#635).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "releases_dir": {"type": "string"},
                                        "only_approved": {"type": "boolean"},
                                    },
                                },
                            },
                            {
                                "name": "plate_release_media_feed",
                                "description": "Feed items for pending release media approval (#635).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {"releases_dir": {"type": "string"}},
                                },
                            },
                            {
                                "name": "plate_release_media_validate_paths",
                                "description": "Check that fragment media paths exist on disk (#635).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {"releases_dir": {"type": "string"}},
                                },
                            },
                            {
                                "name": "plate_release_media_decide",
                                "description": "Approve/reject a media item in-memory (persist by editing fragment) (#635).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "releases_dir": {"type": "string"},
                                        "index": {"type": "integer"},
                                        "path": {"type": "string"},
                                        "url": {"type": "string"},
                                        "decision": {"type": "string"},
                                    },
                                },
                            },
                            {
                                "name": "plate_hybrid_list_kinds",
                                "description": "List hybrid/non-code project kinds (software, docs, marketing, infra, …) (#650).",
                                "inputSchema": {"type": "object", "properties": {}},
                            },
                            {
                                "name": "plate_hybrid_list_artifacts",
                                "description": "List generalized artifact types for hybrid projects (#650).",
                                "inputSchema": {"type": "object", "properties": {}},
                            },
                            {
                                "name": "plate_hybrid_list_validation",
                                "description": "List validation strategies (link check, content lint, visual, IaC plan, …) (#650).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {"kind": {"type": "string"}},
                                },
                            },
                            {
                                "name": "plate_hybrid_detect",
                                "description": "Detect project kind from filesystem signals (#650).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {"repo_root": {"type": "string"}},
                                },
                            },
                            {
                                "name": "plate_hybrid_set_kind",
                                "description": "Persist explicit project kind override (#650).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "kind": {"type": "string"},
                                        "base_dir": {"type": "string"},
                                        "note": {"type": "string"},
                                    },
                                    "required": ["kind"],
                                },
                            },
                            {
                                "name": "plate_hybrid_profile",
                                "description": "Load persisted or detected hybrid project profile (#650).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "base_dir": {"type": "string"},
                                        "repo_root": {"type": "string"},
                                    },
                                },
                            },
                            {
                                "name": "plate_hybrid_contract",
                                "description": "Full contract for a project kind: artifacts, validation, deploy targets (#650).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {"kind": {"type": "string"}},
                                    "required": ["kind"],
                                },
                            },
                            {
                                "name": "plate_hybrid_planning_template",
                                "description": "Q&A planning template tuned to project kind (#650/#628).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {"kind": {"type": "string"}},
                                },
                            },
                            {
                                "name": "plate_hybrid_validation_plan",
                                "description": "Feature-level validation plan for non-code or hybrid work (#650).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "kind": {"type": "string"},
                                        "feature_title": {"type": "string"},
                                        "title": {"type": "string"},
                                        "artifact_types": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                        },
                                    },
                                },
                            },
                            {
                                "name": "plate_hybrid_feed",
                                "description": "Feed items for hybrid project profile detection/confirmation (#650).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "base_dir": {"type": "string"},
                                        "repo_root": {"type": "string"},
                                        "limit": {"type": "integer"},
                                    },
                                },
                            },
                            {
                                "name": "plate_packaging_build",
                                "description": "Build marketplace/release package with media, user narratives, onboarding proof, and planning links (#652). Never publishes.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "version": {"type": "string"},
                                        "releases_dir": {"type": "string"},
                                        "base_dir": {"type": "string"},
                                        "require_approved_media": {"type": "boolean"},
                                        "no_persist": {"type": "boolean"},
                                    },
                                },
                            },
                            {
                                "name": "plate_packaging_list",
                                "description": "List persisted marketplace package builds (#652).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "base_dir": {"type": "string"},
                                        "status": {"type": "string"},
                                        "limit": {"type": "integer"},
                                    },
                                },
                            },
                            {
                                "name": "plate_packaging_get",
                                "description": "Get one marketplace package build by id (#652).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "package_id": {"type": "string"},
                                        "id": {"type": "string"},
                                        "base_dir": {"type": "string"},
                                    },
                                },
                            },
                            {
                                "name": "plate_packaging_render",
                                "description": "Render marketplace package markdown (media + narratives + onboarding) (#652).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "package_id": {"type": "string"},
                                        "id": {"type": "string"},
                                        "version": {"type": "string"},
                                        "releases_dir": {"type": "string"},
                                        "base_dir": {"type": "string"},
                                    },
                                },
                            },
                            {
                                "name": "plate_packaging_decide",
                                "description": "Approve package for human publish or reject (#652). Never publishes credentials/secrets.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "package_id": {"type": "string"},
                                        "id": {"type": "string"},
                                        "decision": {"type": "string"},
                                        "decided_by": {"type": "string"},
                                        "note": {"type": "string"},
                                        "base_dir": {"type": "string"},
                                    },
                                    "required": ["package_id"],
                                },
                            },
                            {
                                "name": "plate_packaging_feed",
                                "description": "Feed items for marketplace packages awaiting review/publish Tasks (#652).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "base_dir": {"type": "string"},
                                        "limit": {"type": "integer"},
                                    },
                                },
                            },
                            {
                                "name": "plate_packaging_plan",
                                "description": "Agent packet for marketplace-package scheduled op (#641/#652).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "version": {"type": "string"},
                                        "releases_dir": {"type": "string"},
                                    },
                                },
                            },
                            {
                                "name": "plate_feature_media_plan",
                                "description": "Plan per-Feature demo GIF capture (test_name + path + steps) (#636).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "feature_number": {"type": "integer"},
                                        "feature_title": {"type": "string"},
                                        "title": {"type": "string"},
                                        "test_name": {"type": "string"},
                                        "caption": {"type": "string"},
                                        "fragment_slug": {"type": "string"},
                                        "quality": {"type": "string"},
                                    },
                                },
                            },
                            {
                                "name": "plate_feature_media_register",
                                "description": "Register record_e2e_gif result for a Feature media plan (#636).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "record_id": {"type": "string"},
                                        "gif_path": {"type": "string"},
                                        "video_path": {"type": "string"},
                                        "size_bytes": {"type": "integer"},
                                        "quality": {"type": "string"},
                                        "capture_result": {"type": "object"},
                                        "submit_for_approval": {"type": "boolean"},
                                    },
                                    "required": ["record_id"],
                                },
                            },
                            {
                                "name": "plate_feature_media_list",
                                "description": "List Feature media registry records (#636).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "status": {"type": "string"},
                                        "feature_number": {"type": "integer"},
                                        "limit": {"type": "integer"},
                                    },
                                },
                            },
                            {
                                "name": "plate_feature_media_get",
                                "description": "Get one Feature media record (#636).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {"record_id": {"type": "string"}},
                                    "required": ["record_id"],
                                },
                            },
                            {
                                "name": "plate_feature_media_decide",
                                "description": "Approve/reject Feature demo media (#636).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "record_id": {"type": "string"},
                                        "decision": {"type": "string"},
                                        "decided_by": {"type": "string"},
                                        "note": {"type": "string"},
                                    },
                                    "required": ["record_id", "decision"],
                                },
                            },
                            {
                                "name": "plate_feature_media_skip",
                                "description": "Skip media requirement for a Feature (#636).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "record_id": {"type": "string"},
                                        "note": {"type": "string"},
                                    },
                                    "required": ["record_id"],
                                },
                            },
                            {
                                "name": "plate_feature_media_attach_fragment",
                                "description": "Append approved media to unreleased fragment media[] (#636/#635).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "record_id": {"type": "string"},
                                        "fragment_path": {"type": "string"},
                                        "fragment": {"type": "string"},
                                    },
                                    "required": ["record_id", "fragment_path"],
                                },
                            },
                            {
                                "name": "plate_feature_media_feed",
                                "description": "Feed presentation for planned/pending Feature media (#636).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {"limit": {"type": "integer"}},
                                },
                            },
                            {
                                "name": "plate_scheduled_ops_list",
                                "description": "List scheduled autonomous ops catalog (#641).",
                                "inputSchema": {"type": "object", "properties": {}},
                            },
                            {
                                "name": "plate_scheduled_ops_status",
                                "description": "Runnable vs gated scheduled ops at current risk_tolerance (#641).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {"risk_tolerance": {"type": "string"}},
                                },
                            },
                            {
                                "name": "plate_scheduled_op_plan",
                                "description": "Emit agent step packet for a scheduled op (#641).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "op_id": {"type": "string"},
                                        "dry_run": {"type": "boolean"},
                                    },
                                    "required": ["op_id"],
                                },
                            },
                            {
                                "name": "plate_scheduled_op_run",
                                "description": "Run/record scheduled op (dry_run default; high/critical need approved) (#641).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "op_id": {"type": "string"},
                                        "dry_run": {"type": "boolean"},
                                        "risk_tolerance": {"type": "string"},
                                        "approved": {"type": "boolean"},
                                        "checkpoint_id": {"type": "string"},
                                        "note": {"type": "string"},
                                    },
                                    "required": ["op_id"],
                                },
                            },
                            {
                                "name": "plate_scheduled_op_runs",
                                "description": "List scheduled op runs (#641).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "op_id": {"type": "string"},
                                        "status": {"type": "string"},
                                        "limit": {"type": "integer"},
                                    },
                                },
                            },
                            {
                                "name": "plate_scheduled_op_complete",
                                "description": "Mark a scheduled op run done/cancelled (#641).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "run_id": {"type": "string"},
                                        "status": {"type": "string"},
                                        "note": {"type": "string"},
                                    },
                                    "required": ["run_id"],
                                },
                            },
                            {
                                "name": "plate_scheduled_ops_feed",
                                "description": "Feed items for gated scheduled ops needing human (#641).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "risk_tolerance": {"type": "string"},
                                        "limit": {"type": "integer"},
                                    },
                                },
                            },
                            {
                                "name": "plate_task_create",
                                "description": "Create a human-only Task issue with the 6-field contract (#359). Redacts secret-looking text. Agents never complete the human work.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "repo": {"type": "string"},
                                        "title": {"type": "string"},
                                        "human_action": {"type": "string"},
                                        "why_agent_cannot": {"type": "string"},
                                        "context": {"type": "string"},
                                        "instructions": {"type": "string"},
                                        "done_signal": {"type": "string"},
                                        "related_links": {"type": "string"},
                                        "milestone": {"type": "string"},
                                        "epic_milestone": {"type": "string"},
                                        "dry_run": {"type": "boolean"},
                                    },
                                    "required": ["title", "human_action", "why_agent_cannot", "context", "instructions"],
                                },
                            },
                            {
                                "name": "plate_task_close",
                                "description": "Close a Task with <!-- PLATE-TASK-CLOSED --> after human completion (#359). Do not invent completion.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "repo": {"type": "string"},
                                        "number": {"type": "integer"},
                                        "comment": {"type": "string"},
                                        "dry_run": {"type": "boolean"},
                                    },
                                    "required": ["number"],
                                },
                            },
                            {
                                "name": "plate_task_detect",
                                "description": "Detect human-only blockers (credentials, PyPI, billing, marketplace, external accounts) and optionally create Task issues (#360). Default detect-only (create=false, dry_run=true).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "repo": {"type": "string"},
                                        "text": {"type": "string"},
                                        "signal": {"type": "string"},
                                        "signals": {"type": "array", "items": {"type": "string"}},
                                        "context": {"type": "string"},
                                        "create": {"type": "boolean"},
                                        "dry_run": {"type": "boolean"},
                                    },
                                },
                            },
                            {
                                "name": "plate_collab_check",
                                "description": "Human/agent co-existence policy check (#643/#651): gate actions against driver:* labels, authorship mix, path/branch ownership, and worktree etiquette.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "action": {"type": "string"},
                                        "labels": {"type": "array", "items": {"type": "string"}},
                                        "author_login": {"type": "string"},
                                        "pr_number": {"type": "integer"},
                                        "commits": {"type": "array", "items": {"type": "object"}},
                                        "paths": {"type": "array", "items": {"type": "string"}},
                                        "branch": {"type": "string"},
                                        "worktree_root": {"type": "string"},
                                        "repo_root": {"type": "string"},
                                    },
                                    "required": ["action"],
                                },
                            },
                            {
                                "name": "plate_collab_issue_status",
                                "description": "Summarize driver:* / pause-delegation state for an issue (#643).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "issue": {"type": "object"},
                                        "labels": {"type": "array", "items": {"type": "string"}},
                                    },
                                },
                            },
                            {
                                "name": "plate_collab_ownership_claim",
                                "description": "Claim path or branch ownership to pause agent autonomy on that surface (#651). Durable under .agentic/collab/ownership.json.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "kind": {"type": "string", "description": "path|branch"},
                                        "target": {"type": "string"},
                                        "owner": {"type": "string", "description": "human|agent|collaborative"},
                                        "reason": {"type": "string"},
                                        "related_issue": {"type": "integer"},
                                        "actor": {"type": "string"},
                                    },
                                    "required": ["target"],
                                },
                            },
                            {
                                "name": "plate_collab_ownership_release",
                                "description": "Release a path/branch ownership claim by id or kind+target (#651).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "claim_id": {"type": "string"},
                                        "id": {"type": "string"},
                                        "kind": {"type": "string"},
                                        "target": {"type": "string"},
                                    },
                                },
                            },
                            {
                                "name": "plate_collab_ownership_list",
                                "description": "List ownership claims (default open) (#651).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "status": {"type": "string"},
                                        "kind": {"type": "string"},
                                        "limit": {"type": "integer"},
                                    },
                                },
                            },
                            {
                                "name": "plate_collab_etiquette",
                                "description": "Branch/worktree etiquette check for agents (#651): integration branch + isolation.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "branch": {"type": "string"},
                                        "worktree_root": {"type": "string"},
                                        "repo_root": {"type": "string"},
                                    },
                                    "required": ["branch"],
                                },
                            },
                            {
                                "name": "plate_collab_concurrent",
                                "description": "Predict concurrent-edit risk from open ownership claims for given paths (#651).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "paths": {"type": "array", "items": {"type": "string"}},
                                    },
                                    "required": ["paths"],
                                },
                            },
                            {
                                "name": "plate_collab_ownership_feed",
                                "description": "Feed presentation items for open human/collaborative ownership pauses (#651).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "limit": {"type": "integer"},
                                    },
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
