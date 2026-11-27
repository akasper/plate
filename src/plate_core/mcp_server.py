"""MCP stdio server for Product Lifecycle Automation Toolkit and Engine (PLATE) / plate_core."""

from __future__ import annotations

import contextlib
import io
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
from .pr_babysit import (
    babysit_pr,
    get_actionable_review_threads,
    get_pr_merge_gates,
    get_unresolved_review_threads,
    resolve_review_thread,
)
from .pr_packet import build_pr_packet
from .pr_verify import verify_pr
from .plate_config import apply_plate_config_upgrade, get_plate_config_report, init_plate_config
from .release import (
    cleanup_dead_branches,
    get_release_notes_diff,
    get_release_status,
    get_release_target_epic_guidance,
)
from .migration import generate_migration_plan, apply_migration_plan
from .migrate_docs_namespace import migrate_docs_namespace
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
from .ledger import (
    get_decision,
    ledger_summary,
    list_decisions,
    query_decisions,
    record_decision,
    record_jev_score,
    record_spend_interval,
)
from .feed import get_user_feed
from .planning import (
    apply_planning_answer,
    build_plan_from_session,
    decide_pending_plan,
    get_plan_history,
    get_planning_script,
    list_actionable_plans,
    list_pending_plans,
    planning_feed_items,
    resubmit_pending_plan,
    start_planning_session,
)
from .epic_release_planning import (
    apply_er_answer,
    build_er_plan_from_session,
    decide_er_plan,
    er_planning_feed_items,
    get_er_script,
    resubmit_er_plan,
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
    tick_pm_loops,
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
    estimate_feature_media_cost,
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
from .mcp.arg_confinement import confine_tool_arguments, resolve_mcp_path
from .mcp.path_confinement import client_safe_error_message, confined, session_repo_root
from .mcp.registry import register_tool_executor
from .mcp.tool_profiles import (
    assert_tool_allowed,
    configure_mcp_tool_profiles,
    filter_tool_definitions,
    get_active_mcp_tool_profiles,
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
    """What Next? for PLATE process (#282 / #654 harden).

    Prefers budget critical/exhausted, open release PRs to babysit, then
    labels/bootstrap, open Epics, pending fragments. Uses health + durable
    budget snapshot; risk_off does not hide budget pressure (#787/#785).
    """
    try:
        from .what_next import get_what_next

        return get_what_next(repo, agent_type)
    except Exception as exc:
        return {"next_action": "inspect with plate_health + plate_epic_status", "error": str(exc)}


def _execute_mcp_tool(name: str | None, args: dict) -> object:
    root = session_repo_root()
    if name:
        assert_tool_allowed(str(name))
        args = confine_tool_arguments(str(name), dict(args), root)
    if name == "plate_health":
        report = get_health(
        args.get("repo"),
        repo_root=str(resolve_mcp_path(args, "repo_root", ".", root)),
        include_spec_audit=not bool(args.get("no_spec_audit", False)),
        )
        payload = report.to_dict()
    elif name == "plate_epic_status":
        report = get_epic_status(args.get("repo"))
        payload = report.to_dict()
    elif name == "init_playwright":
        payload = InitPlaywrightTool.execute(
            str(resolve_mcp_path(args, "repo_path", ".", root)),
            args.get("template_repo"),
            bool(args.get("force", False)),
            repo_root=root,
            confine_template=args.get("template_repo") is not None,
        )
    elif name == "record_e2e_gif":
        test_name = args.get("test_name")
        if not test_name:
            raise ValueError("test_name is required")
        allowed_quality = {"low", "medium", "high"}
        quality = str(args.get("quality", "medium"))
        if quality not in allowed_quality:
            raise ValueError(f"quality must be one of {sorted(allowed_quality)}")
        payload = RecordE2eGifTool.execute(
            str(resolve_mcp_path(args, "repo_path", ".", root)),
            test_name,
            quality,
            start=args.get("start"),
            duration=args.get("duration"),
            repo_root=root,
        )
    elif name == "validate_e2e_tests":
        payload = ValidateE2eTestsTool.execute(
            str(resolve_mcp_path(args, "repo_path", ".", root)),
            repo_root=root,
        )
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
        adopt_arg = args.get("adopt")
        if adopt_arg is None and args.get("existing_repo") is not None:
            adopt_arg = args.get("existing_repo")
        adopt_flag: bool | None
        if adopt_arg is True or adopt_arg is False:
            adopt_flag = bool(adopt_arg)
        else:
            adopt_flag = None
        payload = run_bootstrap(
            args.get("repo"),
            apply_mode=bool(args.get("apply", False)),
            adopt=adopt_flag,
            local_root=args.get("local_root"),
            platform=args.get("platform"),
        ).to_dict()
    elif name == "plate_adoption_status":
        from .adoption import assess_adoption_readiness

        payload = assess_adoption_readiness(
            resolve_mcp_path(args, "repo_root", ".", root),
            include_optional=not bool(args.get("no_optional", False)),
        )
    elif name == "plate_adoption_first_qa_plan":
        from .adoption import plan_first_qa_seed

        payload = plan_first_qa_seed(
            resolve_mcp_path(args, "repo_root", ".", root),
            apply=bool(args.get("apply", False)),
            runner=None,
        )
    elif name == "plate_adoption_session":
        from .adoption import (
            adoption_session_status,
            complete_adoption_session,
            start_adoption_session,
        )

        action = str(args.get("action") or "status").lower()
        root = resolve_mcp_path(args, "repo_root", ".", root)
        if action == "start":
            payload = start_adoption_session(root, force=bool(args.get("force", False)))
        elif action == "complete":
            payload = complete_adoption_session(
                repo_root,
                require_core_ready=bool(args.get("require_core_ready", False)),
            )
        else:
            payload = adoption_session_status(repo_root)
    elif name == "plate_self_migrate_plan":
        from .self_migrate import plan_self_migrate

        payload = plan_self_migrate(
            resolve_mcp_path(args, "repo_root", ".", root),
            target_version=args.get("target_version"),
            include_payload=not bool(args.get("no_payload", False)),
            resolve_upstream=bool(args.get("resolve_upstream", False)),
            allow_network=bool(args.get("allow_network", False)),
        )
    elif name == "plate_self_migrate_merge_markers":
        from .self_migrate import plan_marker_merge

        paths = args.get("paths")
        if isinstance(paths, str):
            paths = [paths]
        payload = plan_marker_merge(
            resolve_mcp_path(args, "repo_root", ".", root),
            paths=paths,
            upstream_root=(
                args.get("upstream_root")
                or args.get("upstream_dir")
                or resolve_mcp_path(args, "upstream_root", ".", root)
            ),
            apply=bool(args.get("apply", False)),
        )
    elif name == "plate_self_migrate_pr_plan":
        from .self_migrate import apply_self_migrate_pr, plan_self_migrate_pr

        pr_plan = plan_self_migrate_pr(
            resolve_mcp_path(args, "repo_root", ".", root),
            target_version=args.get("target_version"),
            include_payload=not bool(args.get("no_payload", False)),
            resolve_upstream=bool(args.get("resolve_upstream", False)),
            allow_network=bool(args.get("allow_network", False)),
            base=args.get("base") or "release",
            closes=args.get("closes"),
        )
        if bool(args.get("apply", False)):
            payload = {
                "plan": pr_plan,
                "apply": apply_self_migrate_pr(
                    pr_plan,
                    dry_run=False,
                    allow_high_risk=bool(args.get("allow_high_risk", False)),
                    runner=None,
                ),
            }
        else:
            payload = pr_plan
    elif name == "plate_self_migrate_verify":
        from .self_migrate import verify_self_migrate

        payload = verify_self_migrate(
            resolve_mcp_path(args, "repo_root", ".", root),
            target_version=args.get("target_version"),
            include_payload=not bool(args.get("no_payload", False)),
            resolve_upstream=bool(args.get("resolve_upstream", False)),
            allow_network=bool(args.get("allow_network", False)),
        )
    elif name == "plate_config_get":
        payload = get_plate_config_report(resolve_mcp_path(args, "repo_root", ".", root)).to_dict()
    elif name == "plate_config_validate":
        payload = get_plate_config_report(resolve_mcp_path(args, "repo_root", ".", root)).to_dict()
    elif name == "plate_config_init":
        payload = init_plate_config(resolve_mcp_path(args, "repo_root", ".", root), force=bool(args.get("force", False))).to_dict()
    elif name == "plate_config_upgrade":
        payload = apply_plate_config_upgrade(
            resolve_mcp_path(args, "repo_root", ".", root),
            apply=bool(args.get("apply", False)),
        ).to_dict()
    elif name == "plate_hooks_install":
        from .git_hooks import install_git_hook

        hook = str(args.get("hook") or "pre-push")
        try:
            report = install_git_hook(
                hook,
                resolve_mcp_path(args, "repo_root", ".", root),
                force=bool(args.get("force", False)),
            )
            payload = {"ok": True, **report.to_dict()}
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            payload = {"ok": False, "error": str(exc)}
    elif name == "plate_hooks_status":
        from .git_hooks import git_hooks_status

        payload = git_hooks_status(resolve_mcp_path(args, "repo_root", ".", root)).to_dict()
    elif name == "plate_plan_epic":
        payload = _plan_epic_stub(args).to_dict()
    elif name == "plate_planning_start":
        br = args.get("budget_remaining")
        if br is not None:
            try:
                br = int(br)
            except (TypeError, ValueError):
                br = None
        use_live = args.get("use_live_budget")
        if use_live is None:
            use_live = True
        payload = start_planning_session(
            str(args.get("kind") or "feature"),
            budget_remaining=br,
            use_live_budget=bool(use_live),
        )
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
        br = args.get("budget_remaining")
        if br is not None:
            try:
                br = int(br)
            except (TypeError, ValueError):
                br = None
        use_live = args.get("use_live_budget")
        if use_live is None:
            use_live = True
        payload = build_plan_from_session(
            session if isinstance(session, dict) else {},
            budget_remaining=br,
            use_live_budget=bool(use_live),
        )
    elif name == "plate_planning_script":
        payload = get_planning_script(str(args.get("kind") or "feature"))
    elif name == "plate_planning_decide":
        payload = decide_pending_plan(
            str(args.get("plan_id") or args.get("id") or ""),
            str(args.get("decision") or "approve"),
            note=str(args.get("note") or ""),
            decided_by=str(args.get("decided_by") or args.get("by") or "mcp"),
        )
    elif name == "plate_planning_resubmit":
        payload = resubmit_pending_plan(
            str(args.get("plan_id") or args.get("id") or ""),
            title=args.get("title"),
            body=args.get("body"),
            note=str(args.get("note") or ""),
            resubmitted_by=str(args.get("resubmitted_by") or args.get("by") or "mcp"),
        )
    elif name == "plate_planning_history":
        payload = {
            "history": get_plan_history(
                str(args.get("plan_id") or args.get("id") or ""),
                limit=int(args.get("limit") or 20),
            )
        }
    elif name == "plate_planning_list_pending":
        if args.get("feed"):
            payload = {"feed": planning_feed_items(limit=int(args.get("limit") or 20))}
        elif args.get("actionable"):
            payload = {
                "actionable": list_actionable_plans(limit=int(args.get("limit") or 20))
            }
        else:
            payload = {
                "pending": list_pending_plans(limit=int(args.get("limit") or 20))
            }
    elif name == "plate_er_planning_start":
        br = args.get("budget_remaining")
        if br is not None:
            try:
                br = int(br)
            except (TypeError, ValueError):
                br = None
        use_live = args.get("use_live_budget")
        if use_live is None:
            use_live = True
        payload = start_er_session(
            str(args.get("kind") or "epic"),
            budget_remaining=br,
            use_live_budget=bool(use_live),
        )
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
        br = args.get("budget_remaining")
        if br is not None:
            try:
                br = int(br)
            except (TypeError, ValueError):
                br = None
        use_live = args.get("use_live_budget")
        if use_live is None:
            use_live = True
        payload = build_er_plan_from_session(
            session if isinstance(session, dict) else {},
            budget_remaining=br,
            use_live_budget=bool(use_live),
        )
    elif name == "plate_er_planning_script":
        payload = get_er_script(str(args.get("kind") or "epic"))
    elif name == "plate_er_planning_decide":
        payload = decide_er_plan(
            str(args.get("plan_id") or args.get("id") or ""),
            str(args.get("decision") or "approve"),
            note=str(args.get("note") or ""),
            decided_by=str(args.get("decided_by") or args.get("by") or "mcp"),
        )
    elif name == "plate_er_planning_resubmit":
        payload = resubmit_er_plan(
            str(args.get("plan_id") or args.get("id") or ""),
            title=args.get("title"),
            body=args.get("body"),
            note=str(args.get("note") or ""),
            resubmitted_by=str(args.get("resubmitted_by") or args.get("by") or "mcp"),
        )
    elif name == "plate_er_planning_list_pending":
        payload = {
            "items": er_planning_feed_items(limit=int(args.get("limit") or 20))
        }
    elif name == "plate_artifact_propose":
        br = args.get("budget_remaining")
        if br is not None:
            try:
                br = int(br)
            except (TypeError, ValueError):
                br = None
        use_live = args.get("use_live_budget")
        if use_live is None:
            use_live = True
        payload = propose_artifact(
            kind=str(args.get("kind") or "design"),
            title=str(args.get("title") or "Artifact"),
            summary=str(args.get("summary") or ""),
            content_path=(
                resolve_mcp_path(args, "content_path", ".", root)
                if args.get("content_path")
                else ""
            ),
            content_excerpt=str(args.get("content_excerpt") or ""),
            related_issue=args.get("related_issue"),
            related_epic=args.get("related_epic"),
            originating_question=args.get("originating_question"),
            media_links=list(args.get("media_links") or []),
            actor=str(args.get("actor") or "agent"),
            budget_remaining=br,
            use_live_budget=bool(use_live),
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
        br = args.get("budget_remaining")
        if br is not None:
            try:
                br = int(br)
            except (TypeError, ValueError):
                br = None
        use_live = args.get("use_live_budget")
        if use_live is None:
            use_live = True
        payload = resubmit_proposal(
            str(args.get("proposal_id") or args.get("id") or ""),
            summary=args.get("summary"),
            content_path=args.get("content_path") or None,
            content_excerpt=args.get("content_excerpt"),
            media_links=list(args.get("media_links") or []) if args.get("media_links") is not None else None,
            title=args.get("title"),
            actor=str(args.get("actor") or "agent"),
            budget_remaining=br,
            use_live_budget=bool(use_live),
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
    elif name == "plate_pr_verify":
        pr_number = args.get("pr_number")
        if pr_number is None:
            raise ValueError("pr_number is required")
        pr_number = int(pr_number)
        if pr_number <= 0:
            raise ValueError("pr_number must be > 0")
        root = session_repo_root()
        payload = verify_pr(
            pr_number=pr_number,
            repo=args.get("repo"),
            run_tests=bool(args.get("run_tests", False)),
            repo_root=str(root) if bool(args.get("run_tests", False)) else None,
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
    elif name == "plate_pr_evidence":
        from .plate_evidence import run_plate_evidence

        pr_number = args.get("pr_number")
        if pr_number is None:
            raise ValueError("pr_number is required")
        pr_number = int(pr_number)
        body_file = args.get("body_file")
        if not body_file:
            raise ValueError("body_file is required")
        images = args.get("images") or []
        if not isinstance(images, list) or not images:
            raise ValueError("images must be a non-empty array")
        result = run_plate_evidence(
            pr_number,
            str(body_file),
            [str(p) for p in images],
            gh=args.get("gh"),
        )
        payload = result.to_dict()
    elif name == "plate_pr_packet":
        pr_number = args.get("pr_number")
        if pr_number is None:
            raise ValueError("pr_number is required")
        pr_number = int(pr_number)
        if pr_number <= 0:
            raise ValueError("pr_number must be > 0")
        result = build_pr_packet(
            pr_number=pr_number,
            repo=args.get("repo"),
            max_bytes=int(args.get("max_bytes") or 6144),
            record_ledger=bool(args.get("record_ledger", False)),
            turns=args.get("turns"),
            run_id=args.get("run_id"),
            cloud_agent_id=args.get("cloud_agent_id"),
        )
        payload = json.loads(result.json_text)
    elif name == "plate_get_unresolved_review_threads":
        pr_number = args.get("pr_number")
        if pr_number is None:
            raise ValueError("pr_number is required")
        pr_number = int(pr_number)
        if pr_number <= 0:
            raise ValueError("pr_number must be > 0")
        payload = {
            "repo": args.get("repo"),
            "pr_number": pr_number,
            "threads": get_unresolved_review_threads(
                pr_number=pr_number,
                repo=args.get("repo"),
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
            releases_dir=Path(
                resolve_mcp_path(args, "releases_dir", ".agentic/releases", root)
            )
            if releases_dir_arg is not None
            else None,
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
            releases_dir=Path(resolve_mcp_path(args, "releases_dir", ".agentic/releases", root))
            if releases_dir_arg is not None
            else None,
        ).to_dict()
    elif name == "plate_costs":
        from pathlib import Path as _LedgerPath

        ledger_base = _LedgerPath(
            resolve_mcp_path(args, "ledger_base_dir", ".agentic/ledger", root)
        )
        if args.get("run_cost"):
            from .costs import compute_run_all_in_cost

            payload = compute_run_all_in_cost(
                run_id=args.get("run_id"),
                cloud_agent_id=args.get("cloud_agent_id"),
                base_dir=ledger_base,
            )
        elif args.get("spend_report") or args.get("spend_attribution"):
            from .costs import get_spend_attribution_report

            payload = get_spend_attribution_report(
                base_dir=ledger_base,
                limit=int(args.get("limit") or 500),
            )
        elif args.get("dashboard"):
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
        if bool(args.get("reset")):
            from .autonomy import reset_budget_spend

            payload = reset_budget_spend(
                reason=str(args.get("reset_reason") or "mcp plate_autonomy_budget reset=true"),
            )
        else:
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
    elif name == "plate_pm_tick_loops":
        payload = tick_pm_loops(
            args.get("repo"),
            dry_run=bool(args.get("dry_run", True)),
            fetch_gates=bool(args.get("fetch_gates") or args.get("fetch_loop_gates") or False),
            limit=int(args.get("limit") or 20),
            complete_when_done=bool(args.get("complete_when_done", True)),
        )
    elif name == "plate_fleet_status":
        br = args.get("budget_remaining")
        if br is None:
            br = args.get("budget_tokens")
        if br is not None:
            try:
                br = int(br)
            except (TypeError, ValueError):
                br = None
        use_live = args.get("use_live_budget")
        if use_live is None:
            use_live = True
        payload = fleet_status(
            budget_remaining=br,
            use_live_budget=bool(use_live),
            risk_tolerance=str(args.get("risk_tolerance") or args.get("risk") or "medium"),
        )
    elif name == "plate_fleet_roles":
        payload = {"roles": list_fleet_roles()}
    elif name == "plate_fleet_handoff":
        br = args.get("budget_remaining")
        if br is not None:
            try:
                br = int(br)
            except (TypeError, ValueError):
                br = None
        use_live = args.get("use_live_budget")
        if use_live is None:
            use_live = True
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
            budget_remaining=br,
            use_live_budget=bool(use_live),
        )
    elif name == "plate_fleet_update":
        payload = update_handoff(
            str(args.get("handoff_id") or args.get("id") or ""),
            status=args.get("status"),
            notes=args.get("notes") or args.get("note"),
            artifacts=list(args.get("artifacts") or []) or None,
            context_patch=args.get("context") if isinstance(args.get("context"), dict) else None,
            shadow_ack=args.get("shadow_ack") or None,
            approved=bool(args.get("approved") or False),
            checkpoint_id=args.get("checkpoint_id") or None,
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
        bt = args.get("budget_tokens")
        if bt is not None:
            try:
                bt = int(bt)
            except (TypeError, ValueError):
                bt = None
        use_live = args.get("use_live_budget")
        if use_live is None:
            use_live = True
        payload = plan_fleet_from_intent(
            str(args.get("intent") or args.get("task") or ""),
            budget_tokens=bt,
            risk_tolerance=str(args.get("risk_tolerance") or args.get("risk") or "medium"),
            related_issue=args.get("related_issue"),
            create=bool(args.get("create") or args.get("apply") or False),
            use_live_budget=bool(use_live),
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
        br = args.get("budget_remaining")
        if br is not None:
            try:
                br = int(br)
            except (TypeError, ValueError):
                br = None
        use_live = args.get("use_live_budget")
        if use_live is None:
            use_live = True
        if dry:
            payload = run_discussion_review_procedure(
                repo=args.get("repo"),
                discussions=list(discussions) if discussions else None,
                dry_run=True,
                fetch_live=False,
                budget_remaining=br,
                use_live_budget=bool(use_live),
            )
        else:
            payload = review_discussions(
                list(discussions) if discussions else None,
                repo=args.get("repo"),
                persist=bool(args.get("persist", True)),
                fetch_live=bool(args.get("fetch_live", False)),
                min_score=float(args.get("min_score") or 30),
                limit=int(args.get("limit") or 10),
                budget_remaining=br,
                use_live_budget=bool(use_live),
            )
    elif name == "plate_monitor_market":
        signals = args.get("signals") or []
        if isinstance(signals, str):
            try:
                signals = json.loads(signals)
            except Exception:
                signals = [{"title": signals}]
        dry = bool(args.get("dry_run", True))
        br = args.get("budget_remaining")
        if br is not None:
            try:
                br = int(br)
            except (TypeError, ValueError):
                br = None
        use_live = args.get("use_live_budget")
        if use_live is None:
            use_live = True
        if dry:
            payload = run_market_monitor_procedure(
                signals=list(signals),
                dry_run=True,
                budget_remaining=br,
                use_live_budget=bool(use_live),
            )
        else:
            payload = monitor_market_signals(
                list(signals),
                persist=bool(args.get("persist", True)),
                min_score=float(args.get("min_score") or 40),
                limit=int(args.get("limit") or 10),
                budget_remaining=br,
                use_live_budget=bool(use_live),
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
        br = args.get("budget_remaining")
        if br is not None:
            try:
                br = int(br)
            except (TypeError, ValueError):
                br = None
        use_live = args.get("use_live_budget")
        if use_live is None:
            use_live = True
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
            budget_remaining=br,
            use_live_budget=bool(use_live),
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
        br = args.get("budget_remaining")
        if br is not None:
            try:
                br = int(br)
            except (TypeError, ValueError):
                br = None
        use_live = args.get("use_live_budget")
        if use_live is None:
            use_live = True
        payload = create_stub_issue(
            args.get("draft_id") or args.get("id"),
            repo=args.get("repo"),
            dry_run=bool(args.get("dry_run", True)),
            budget_remaining=br,
            use_live_budget=bool(use_live),
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
        br = args.get("budget_remaining")
        if br is not None:
            try:
                br = int(br)
            except (TypeError, ValueError):
                br = None
        use_live = args.get("use_live_budget")
        if use_live is None:
            use_live = True
        payload = author_and_create(
            str(args.get("intent") or ""),
            issue_type=args.get("issue_type") or args.get("type"),
            title=args.get("title"),
            dry_run=bool(args.get("dry_run", True)),
            repo=args.get("repo"),
            summary=args.get("summary"),
            source=str(args.get("source") or "qa"),
            parent_epic=args.get("parent_epic"),
            budget_remaining=br,
            use_live_budget=bool(use_live),
        )
    elif name == "plate_stub_feed":
        payload = {"items": stubs_feed_items(limit=int(args.get("limit") or 10))}
    elif name == "plate_bug_loop_start":
        labels = args.get("labels") or []
        if isinstance(labels, str):
            labels = [x.strip() for x in labels.split(",") if x.strip()]
        use_live = args.get("use_live_budget")
        if use_live is None:
            use_live = True
        payload = start_bug_loop(
            bug_number=args.get("bug_number") or args.get("bug"),
            bug_title=str(args.get("bug_title") or args.get("title") or ""),
            risk=str(args.get("risk") or "medium"),
            size=str(args.get("size") or "medium"),
            labels=list(labels) if labels else None,
            paths=list(args.get("paths") or []) or None,
            risk_tolerance=str(args.get("risk_tolerance") or "medium"),
            pr_number=args.get("pr_number") or args.get("pr"),
            branch=args.get("branch"),
            budget_remaining=args.get("budget_remaining"),
            use_live_budget=bool(use_live),
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
        br = args.get("budget_remaining")
        if br is not None:
            try:
                br = int(br)
            except (TypeError, ValueError):
                br = None
        use_live = args.get("use_live_budget")
        if use_live is None:
            use_live = True
        payload = propose_contract(
            feature_number=args.get("feature_number") or args.get("feature"),
            feature_title=str(args.get("feature_title") or args.get("title") or ""),
            visual_specs=list(args.get("visual_specs") or []) or None,
            interaction_criteria=list(args.get("interaction_criteria") or []) or None,
            a11y_criteria=list(args.get("a11y_criteria") or []) or None,
            artifact_paths=list(args.get("artifact_paths") or []) or None,
            has_playwright=bool(args.get("has_playwright") or False),
            submit_for_approval=bool(args.get("submit_for_approval", True)),
            budget_remaining=br,
            use_live_budget=bool(use_live),
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

        rdir = _P(resolve_mcp_path(args, "releases_dir", ".agentic/releases", root))
        frags = collect_release_fragments(rdir)
        payload = build_media_manifest(frags, version=args.get("version"))
    elif name == "plate_release_media_render":
        from pathlib import Path as _P

        rdir = _P(resolve_mcp_path(args, "releases_dir", ".agentic/releases", root))
        media = collect_release_media(collect_release_fragments(rdir))
        payload = {
            "markdown": render_media_markdown(
                media, only_approved=bool(args.get("only_approved") or False)
            ),
            "n": len(media),
        }
    elif name == "plate_release_media_feed":
        from pathlib import Path as _P

        rdir = _P(resolve_mcp_path(args, "releases_dir", ".agentic/releases", root))
        media = collect_release_media(collect_release_fragments(rdir))
        payload = {"items": media_feed_items(media)}
    elif name == "plate_release_media_validate_paths":
        from pathlib import Path as _P

        rdir = _P(resolve_mcp_path(args, "releases_dir", ".agentic/releases", root))
        media = collect_release_media(collect_release_fragments(rdir))
        payload = validate_media_paths(media, repo_root=_P("."))
    elif name == "plate_release_media_decide":
        from pathlib import Path as _P

        rdir = _P(resolve_mcp_path(args, "releases_dir", ".agentic/releases", root))
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

        payload = detect_project_kind(_P(resolve_mcp_path(args, "repo_root", ".", root)))
    elif name == "plate_hybrid_set_kind":
        from pathlib import Path as _P

        base_dir = _P(resolve_mcp_path(args, "base_dir", ".agentic/hybrid", root))
        payload = set_project_kind(
            str(args.get("kind") or ""),
            base_dir=base_dir,
            note=str(args.get("note") or ""),
        )
    elif name == "plate_hybrid_profile":
        from pathlib import Path as _P

        base_dir = _P(resolve_mcp_path(args, "base_dir", ".agentic/hybrid", root))
        repo_root = _P(resolve_mcp_path(args, "repo_root", ".", root))
        payload = load_project_profile(
            base_dir=base_dir,
            repo_root=repo_root,
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
                base_dir=_P(resolve_mcp_path(args, "base_dir", ".agentic/hybrid", root)),
                repo_root=_P(str(resolve_mcp_path(args, "repo_root", ".", root))),
                limit=int(args.get("limit") or 4),
            )
        }
    elif name == "plate_packaging_build":
        from pathlib import Path as _P

        rdir = _P(resolve_mcp_path(args, "releases_dir", ".agentic/releases", root))
        bdir = _P(resolve_mcp_path(args, "base_dir", ".agentic/packaging", root))
        frags = collect_release_fragments(rdir)
        br = args.get("budget_remaining")
        if br is not None:
            try:
                br = int(br)
            except (TypeError, ValueError):
                br = None
        use_live = args.get("use_live_budget")
        if use_live is None:
            use_live = True
        payload = build_package(
            str(args.get("version") or "unreleased"),
            frags,
            base_dir=bdir,
            require_approved_media=bool(args.get("require_approved_media") or False),
            persist=not bool(args.get("no_persist") or False),
            budget_remaining=br,
            use_live_budget=bool(use_live),
        )
    elif name == "plate_packaging_list":
        from pathlib import Path as _P

        bdir = _P(resolve_mcp_path(args, "base_dir", ".agentic/packaging", root))
        payload = {
            "packages": list_packages(
                base_dir=bdir,
                status=str(args.get("status") or "all"),
                limit=int(args.get("limit") or 20),
            )
        }
    elif name == "plate_packaging_get":
        from pathlib import Path as _P

        bdir = _P(resolve_mcp_path(args, "base_dir", ".agentic/packaging", root))
        p = get_package(str(args.get("package_id") or args.get("id") or ""), base_dir=bdir)
        payload = {"package": p, "ok": p is not None}
    elif name == "plate_packaging_render":
        from pathlib import Path as _P

        bdir = _P(resolve_mcp_path(args, "base_dir", ".agentic/packaging", root))
        pid = str(args.get("package_id") or args.get("id") or "")
        p = get_package(pid, base_dir=bdir) if pid else None
        if p is None and args.get("version"):
            rdir = _P(resolve_mcp_path(args, "releases_dir", ".agentic/releases", root))
            br = args.get("budget_remaining")
            if br is not None:
                try:
                    br = int(br)
                except (TypeError, ValueError):
                    br = None
            use_live = args.get("use_live_budget")
            if use_live is None:
                use_live = True
            built = build_package(
                str(args.get("version")),
                collect_release_fragments(rdir),
                base_dir=bdir,
                persist=False,
                budget_remaining=br,
                use_live_budget=bool(use_live),
            )
            if not built.get("ok"):
                payload = built
            else:
                p = built.get("package")
        if p is not None:
            payload = {
                "ok": True,
                "markdown": render_package_markdown(p),
                "package_id": p.get("id"),
            }
        elif "payload" not in locals():
            payload = {"ok": False, "error": "package not found"}
    elif name == "plate_packaging_decide":
        from pathlib import Path as _P

        bdir = _P(resolve_mcp_path(args, "base_dir", ".agentic/packaging", root))
        payload = decide_package_publish(
            str(args.get("package_id") or args.get("id") or ""),
            str(args.get("decision") or "approve"),
            decided_by=str(args.get("decided_by") or "human"),
            note=str(args.get("note") or ""),
            base_dir=bdir,
        )
    elif name == "plate_packaging_feed":
        from pathlib import Path as _P

        bdir = _P(resolve_mcp_path(args, "base_dir", ".agentic/packaging", root))
        payload = {
            "items": packaging_feed_items(
                base_dir=bdir, limit=int(args.get("limit") or 8)
            )
        }
    elif name == "plate_packaging_plan":
        from pathlib import Path as _P

        payload = plan_marketplace_package_op(
            args.get("version"),
            releases_dir=_P(resolve_mcp_path(args, "releases_dir", ".agentic/releases", root)),
        )
    elif name == "plate_feature_media_estimate_cost":
        payload = estimate_feature_media_cost(
            phase=str(args.get("phase") or "plan"),
            quality=str(args.get("quality") or "medium"),
        )
    elif name == "plate_feature_media_plan":
        br = args.get("budget_remaining")
        use_live = args.get("use_live_budget")
        if use_live is None:
            use_live = True
        payload = plan_feature_media(
            feature_number=args.get("feature_number") or args.get("feature"),
            feature_title=str(args.get("feature_title") or args.get("title") or ""),
            test_name=args.get("test_name"),
            caption=args.get("caption"),
            fragment_slug=args.get("fragment_slug"),
            quality=str(args.get("quality") or "medium"),
            budget_remaining=int(br) if br is not None else None,
            use_live_budget=bool(use_live),
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
        br = args.get("budget_remaining")
        if br is not None:
            try:
                br = int(br)
            except (TypeError, ValueError):
                br = None
        use_live = args.get("use_live_budget")
        if use_live is None:
            use_live = True
        payload = run_scheduled_op(
            str(args.get("op_id") or args.get("id") or ""),
            dry_run=bool(args.get("dry_run", True)),
            risk_tolerance=str(args.get("risk_tolerance") or "medium"),
            approved=bool(args.get("approved") or False),
            checkpoint_id=args.get("checkpoint_id"),
            shadow_ack=args.get("shadow_ack") or None,
            note=str(args.get("note") or ""),
            budget_remaining=br,
            use_live_budget=bool(use_live),
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
            worktree_root=(
                args.get("worktree_root")
                or resolve_mcp_path(args, "worktree_root", ".", root)
            ),
            repo_root=resolve_mcp_path(args, "repo_root", ".", root),
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
            worktree_root=(
                args.get("worktree_root")
                or resolve_mcp_path(args, "worktree_root", ".", root)
            ),
            repo_root=resolve_mcp_path(args, "repo_root", ".", root),
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
    elif name == "plate_ledger_record_spend":
        payload = record_spend_interval(
            cloud_agent_id=args.get("cloud_agent_id"),
            parent_run_id=args.get("parent_run_id"),
            run_id=args.get("run_id"),
            lifecycle_task_type=str(args.get("lifecycle_task_type") or ""),
            model=args.get("model"),
            tier=args.get("tier"),
            effort=args.get("effort"),
            hardware=args.get("hardware"),
            route_clarity=args.get("route_clarity"),
            input_tokens=args.get("input_tokens"),
            output_tokens=args.get("output_tokens"),
            cached_read_tokens=args.get("cached_read_tokens"),
            cache_write_tokens=args.get("cache_write_tokens"),
            tool_output_tokens=args.get("tool_output_tokens"),
            turns=args.get("turns"),
            handoff_packet_size=args.get("handoff_packet_size"),
            handoff_packet_unit=args.get("handoff_packet_unit"),
            rediscovery_count=args.get("rediscovery_count"),
            outcome_accepted=args.get("outcome_accepted"),
            cost_usd=args.get("cost_usd"),
            jev_score=args.get("jev_score"),
            jev_suggested_tier=args.get("jev_suggested_tier"),
            jev_model=args.get("jev_model"),
            jev_route_clarity=args.get("jev_route_clarity"),
            related_issue=args.get("related_issue"),
            related_pr=args.get("related_pr"),
            session=str(args.get("session") or ""),
            metadata=args.get("metadata") if isinstance(args.get("metadata"), dict) else {},
        )
    elif name == "plate_ledger_record_jev":
        payload = record_jev_score(
            jev_score=float(args["jev_score"]),
            run_id=args.get("run_id"),
            cloud_agent_id=args.get("cloud_agent_id"),
            lifecycle_task_type=str(args.get("lifecycle_task_type") or ""),
            jev_suggested_tier=args.get("jev_suggested_tier"),
            jev_model=args.get("jev_model"),
            jev_route_clarity=args.get("jev_route_clarity"),
            tier=args.get("tier"),
            model=args.get("model"),
            route_clarity=args.get("route_clarity"),
            hardware=args.get("hardware"),
            effort=args.get("effort"),
            outcome_accepted=args.get("outcome_accepted"),
            related_issue=args.get("related_issue"),
            related_pr=args.get("related_pr"),
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
    elif name == "plate_migrate_docs_namespace":
        apply_mode = bool(args.get("apply", False))
        target_dir = resolve_mcp_path(args, "target_dir", ".", root)
        plan = migrate_docs_namespace(target_dir=target_dir, apply=apply_mode)
        payload = plan.to_dict()
    elif name == "plate_import_payload":
        from .import_payload import import_payload

        apply_mode = bool(args.get("apply", False))
        dry = bool(args.get("dry_run", True))
        if apply_mode:
            dry = False
        ns = args.get("namespace_scripts")
        if ns is not None:
            ns = bool(ns)
        nd = args.get("namespace_docs")
        if nd is not None:
            nd = bool(nd)
        target_dir = resolve_mcp_path(args, "target_dir", ".", root)
        escape_hatch = args.get("escape_hatch_dir") or args.get("escape_hatch")
        payload = import_payload(
            target_dir=target_dir,
            strategy=str(args.get("strategy") or "safe"),
            template_repo=args.get("template_repo"),
            dry_run=dry,
            apply=apply_mode,
            namespace_scripts=ns,
            namespace_docs=nd,
            escape_hatch_dir=escape_hatch,
            escape_hatch_on_conflict=bool(args.get("escape_hatch_on_conflict", False)),
            platform=args.get("platform"),
        )
    elif name == "plate_payload_list":
        from .payload_surface import list_payload_files

        payload = list_payload_files(
            args.get("template_repo"),
            include_excluded=bool(args.get("include_excluded", False)),
        )
    elif name == "plate_payload_root":
        from .payload_surface import resolve_payload_root

        payload = resolve_payload_root(args.get("template_repo"))
    elif name == "plate_payload_manifest":
        from .payload_surface import show_manifest

        payload = show_manifest()
    elif name == "plate_payload_classify":
        from .payload_surface import classify_path

        payload = classify_path(
            resolve_mcp_path(args, "path", ".", root) if args.get("path") else "",
            args.get("template_repo"),
        )
    elif name == "plate_spec_audit":
        from .spec_audit import audit_spec

        repo_root = resolve_mcp_path(args, "repo_root", ".", root)
        releases_dir = (
            resolve_mcp_path(args, "releases_dir", ".agentic/releases", root)
            if args.get("releases_dir") is not None
            else None
        )
        spec_path = args.get("spec_path") or args.get("spec")
        spec_path = (
            resolve_mcp_path(args, "spec_path", "SPEC.md", root) if spec_path else None
        )
        payload = audit_spec(
            repo_root,
            releases_dir=releases_dir,
            spec_path=spec_path,
        ).to_dict()
    elif name == "plate_spec_audit_followups":
        from .spec_audit import apply_audit_followups, audit_spec

        repo_root = resolve_mcp_path(args, "repo_root", ".", root)
        releases_dir = (
            resolve_mcp_path(args, "releases_dir", ".agentic/releases", root)
            if args.get("releases_dir") is not None
            else None
        )
        spec_path = args.get("spec_path") or args.get("spec")
        spec_path = (
            resolve_mcp_path(args, "spec_path", "SPEC.md", root) if spec_path else None
        )
        report = audit_spec(
            repo_root,
            releases_dir=releases_dir,
            spec_path=spec_path,
        )
        payload = apply_audit_followups(
            report,
            repo=args.get("repo"),
            apply=bool(args.get("apply", False)),
            max_issues=int(args.get("max_issues") or 10),
        )
        payload["audit_counts"] = report.counts
    elif name == "plate_perform_test_coverage_audit":
        from .mcp.audit_tools import PerformTestCoverageAuditTool
        payload = PerformTestCoverageAuditTool.execute(
            repo=args.get("repo"), dry_run=args.get("dry_run", True)
        )
    elif name == "plate_perform_information_audit":
        from .mcp.audit_tools import PerformInformationAuditTool

        payload = PerformInformationAuditTool.execute(
            repo=args.get("repo"),
            scope=str(args.get("scope") or "repo"),
            agent_type=str(args.get("agent_type") or "general"),
            max_questions=int(args.get("max_questions") or 5),
            dry_run=bool(args.get("dry_run", False)),
            include_defaults=bool(args.get("include_defaults", True)),
        )
    elif name == "plate_list_discussions":
        from .discussions import list_discussions

        payload = [
            d.to_dict()
            for d in list_discussions(
                repo=args.get("repo"),
                category=args.get("category"),
                state=args.get("state"),
                per_page=int(args.get("per_page") or 30),
                page=int(args.get("page") or 1),
            )
        ]
    elif name == "plate_get_discussion":
        from .discussions import get_discussion

        num = args.get("number")
        if num is None:
            raise ValueError("number is required")
        payload = get_discussion(repo=args.get("repo"), number=int(num)).to_dict()
    elif name == "plate_list_discussion_comments":
        from .discussions import list_discussion_comments

        num = args.get("number")
        if num is None:
            raise ValueError("number is required")
        payload = [
            c.to_dict()
            for c in list_discussion_comments(
                repo=args.get("repo"),
                number=int(num),
                per_page=int(args.get("per_page") or 30),
            )
        ]
    elif name == "plate_add_discussion_comment":
        from .discussions import add_discussion_comment

        num = args.get("number")
        body = args.get("body")
        if num is None or not body:
            raise ValueError("number and body are required")
        payload = add_discussion_comment(
            repo=args.get("repo"), number=int(num), body=str(body)
        ).to_dict()
    elif name == "plate_create_discussion":
        from .discussions import create_discussion

        title = args.get("title")
        body = args.get("body")
        if not title or not body:
            raise ValueError("title and body are required")
        payload = create_discussion(
            repo=args.get("repo"),
            category_slug=args.get("category_slug"),
            category_id=args.get("category_id"),
            title=str(title),
            body=str(body),
        ).to_dict()
    elif name == "plate_list_discussion_categories":
        from .discussions import list_discussion_categories

        payload = list_discussion_categories(repo=args.get("repo"))
    elif name == "plate_list_open_ideas":
        from .discussions import list_open_ideas

        payload = [d.to_dict() for d in list_open_ideas(repo=args.get("repo"))]
    else:
        raise KeyError(f"Unknown tool: {name}")
    return payload

def _handle_tools_call(req_id: object, params: dict) -> None:
    name = params.get("name")
    args = params.get("arguments", {}) or {}
    try:
        payload = _execute_mcp_tool(name, args)
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
    except KeyError as exc:
        _write(
            {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32601,
                    "message": client_safe_error_message(exc),
                },
            }
        )
    except Exception as exc:
        _write(
            {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": client_safe_error_message(exc),
                        }
                    ],
                    "isError": True,
                },
            }
        )



def run() -> None:
    configure_mcp_tool_profiles()
    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError as exc:
            _write(
                {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": f"Parse error: {exc}"},
                }
            )
            continue
        if not isinstance(req, dict):
            _write(
                {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32600, "message": "Invalid Request"},
                }
            )
            continue
        req_id = req.get("id")
        method = req.get("method")
        if not method:
            if req_id is not None:
                _write(
                    {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {"code": -32600, "message": "Invalid Request"},
                    }
                )
            continue

        if method == "ping":
            _write({"jsonrpc": "2.0", "id": req_id, "result": {}})
            continue

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
            from .mcp.registry import tool_definitions_for_list

            all_tools = tool_definitions_for_list()
            visible_tools = filter_tool_definitions(all_tools, get_active_mcp_tool_profiles())
            _write(
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"tools": visible_tools},
                }
            )
        elif method == "tools/call":
            with contextlib.redirect_stdout(sys.stderr):
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


register_tool_executor(_execute_mcp_tool)

if __name__ == "__main__":
    run()
