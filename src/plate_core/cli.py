"""CLI interface used by gh-plate extension entrypoint."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .bootstrap import run_bootstrap
from .baseline_catalog import (
    BaselineCatalogError,
    DelegationResult,
    delegate_to_agent,
    get_agent,
    get_skill,
    list_agents,
    list_skills,
)
from .context_map import ContextMapError, get_context_route, list_context_routes
from .epics import get_epic_status
from .features import detect_playwright_e2e_local, get_features
from .github_client import GhApiError
from .health import get_health
from .pr_babysit import babysit_pr, get_pr_merge_gates
from .release import (
    cleanup_dead_branches,
    cut_release as core_cut_release,
    get_release_notes_diff,
    get_release_status,
    get_release_target_epic_guidance,
)
from .migration import generate_migration_plan, apply_migration_plan
from .costs import get_cost_report
from .autonomy import AutonomyEngine, get_autonomy_status, run_autonomy_cycle, simulate_autonomy_action
from .checkpoint import create_checkpoint, decide_checkpoint, get_checkpoint, list_checkpoints, list_open_checkpoints
from .ledger import get_decision, list_decisions, query_decisions, record_decision, ledger_summary
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
    complete_pm_assignment,
    get_pm_status,
    tick_pm_loops,
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
)
from .design_validation import (
    build_failing_test_scaffold,
    contract_feed_items,
    decide_contract,
    get_contract,
    list_contracts,
    propose_contract,
    validate_contract_readiness,
)
from .release_media import (
    build_media_manifest,
    collect_release_media,
    decide_media_item,
    media_approval_summary,
    media_feed_items,
    render_media_markdown,
    validate_media_paths,
)
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
)
from .tasks import (
    close_task_with_signal,
    create_task,
    detect_and_create_tasks,
)
from .collab import (
    analyze_pr_authorship,
    branch_etiquette_check,
    claim_ownership,
    collab_policy_check,
    collab_status_for_issue,
    concurrent_edit_risk,
    list_ownership_claims,
    ownership_feed_items,
    release_ownership,
)
from .plate_config import (
    PlateConfigError,
    apply_plate_config_upgrade,
    get_plate_config_report,
    init_plate_config,
    load_plate_config,
)


def cmd_health(args: argparse.Namespace) -> int:
    report = get_health(
        args.repo,
        repo_root=getattr(args, "repo_root", None) or ".",
        include_spec_audit=not bool(getattr(args, "no_spec_audit", False)),
    )
    if args.json:
        print(json.dumps(report.to_dict()))
        return 0

    print(f"Repo: {report.repo}")
    print(f"Status: {report.status.upper()}")
    print(f"Label coverage: {'OK' if report.label_coverage_ok else 'MISSING'}")
    if report.missing_labels:
        print(f"Missing labels: {', '.join(report.missing_labels)}")
    print(f"Branch protection: {'ENABLED' if report.branch_protection_enabled else 'DISABLED'}")
    print(f"Open Epics: {report.open_epic_count}")
    bin_count = report.binary_artifacts_tracked
    bin_status = "CLEAN" if bin_count == 0 else f"FOUND {bin_count} (see #90)"
    print(f"Binary artifacts tracked: {bin_count} ({bin_status})")
    print(f"Goals wiki page: {'PRESENT' if report.goals_page_present else 'MISSING'}")
    print(f"Open Questions: {report.open_question_count}")
    plate_line = f".plate/config: {'PRESENT' if report.plate_config_present else 'MISSING'} (valid: {report.plate_config_valid})"
    if report.plate_config_present:
        plate_line += (
            f" file={report.plate_config_file_version or '(unknown)'}"
            f" resolved={report.plate_config_resolved_version or '(unknown)'}"
            f" upgrade={report.plate_config_upgrade_available}"
        )
        if report.plate_config_enabled_extensions:
            plate_line += f" enabled_extensions={','.join(report.plate_config_enabled_extensions)}"
    print(plate_line)
    print(f"Curiosity answers index: {'PRESENT' if report.curiosity_answers_present else 'MISSING'}")
    if report.budget_remaining_tokens is not None or report.budget_daily_limit is not None:
        burn = report.budget_burn_rate if report.budget_burn_rate is not None else "?"
        pressure = report.budget_pressure or "n/a"
        rem = report.budget_remaining_tokens if report.budget_remaining_tokens is not None else "?"
        daily = report.budget_daily_limit if report.budget_daily_limit is not None else "?"
        spent = report.budget_spent_today if report.budget_spent_today is not None else "?"
        risk = report.budget_risk_tolerance or "?"
        en = "on" if report.budget_enabled else "off"
        pause = getattr(report, "budget_would_pause_next_cycle", None)
        throttle = getattr(report, "budget_would_throttle_next_cycle", None)
        gate = ""
        if pause is not None or throttle is not None:
            gate = f" would_pause={pause} would_throttle={throttle}"
        print(
            f"Budget (#634): remaining={rem}/{daily} spent_today={spent} "
            f"burn={burn}% pressure={pressure} risk={risk} enabled={en}{gate}"
        )
    if report.spec_audit_status:
        counts = report.spec_audit_counts or {}
        act = (
            report.spec_audit_actionable_count
            if report.spec_audit_actionable_count is not None
            else "?"
        )
        print(
            f"SPEC audit (#340): status={report.spec_audit_status} "
            f"actionable={act} counts={counts}"
        )
        if report.spec_audit_next_step:
            print(f"SPEC audit next: {report.spec_audit_next_step}")
    return 0 if report.status != "fail" else 1


def cmd_what_next(args: argparse.Namespace) -> int:
    """Recommend next PLATE process step (#789/#791)."""
    from .what_next import get_what_next

    out = get_what_next(
        getattr(args, "repo", None),
        getattr(args, "agent_type", None) or "general",
        include_prs=not bool(getattr(args, "no_prs", False)),
        include_budget=not bool(getattr(args, "no_budget", False)),
        include_fragments=not bool(getattr(args, "no_fragments", False)),
    )
    if args.json:
        print(json.dumps(out))
        return 0 if not out.get("error") else 1
    print(f"Next: {out.get('next_action')}")
    print(f"Priority: {out.get('priority') or 'n/a'}")
    if out.get("rationale"):
        print(f"Rationale: {out.get('rationale')}")
    snap = out.get("state_snapshot") or {}
    if snap:
        print(
            "State: "
            f"labels_ok={snap.get('label_coverage_ok')} "
            f"epics={snap.get('open_epic_count')} "
            f"prs={snap.get('open_pr_count')} "
            f"budget={snap.get('budget_pressure')} "
            f"remaining={snap.get('budget_remaining_tokens')} "
            f"would_pause={snap.get('would_pause_next_cycle')}"
        )
    if out.get("prompt_segment"):
        print(f"Prompt: {out.get('prompt_segment')}")
    return 0 if not out.get("error") else 1


def cmd_epic_status(args: argparse.Namespace) -> int:
    report = get_epic_status(args.repo)
    if args.json:
        print(json.dumps(report.to_dict()))
        return 0

    print(f"Repo: {report.repo}")
    print(f"Open Epics: {report.open_epic_count}")
    if not report.epics:
        print("No Epic:* labels found.")
        return 0
    for epic in report.epics:
        print(f"- {epic.epic_label}")
        if epic.epic_issue_number is not None:
            print(
                f"  Epic issue: #{epic.epic_issue_number} ({(epic.epic_issue_state or 'unknown').upper()})"
                f" {epic.epic_issue_title or ''}".rstrip()
            )
        print(f"  Children: open={epic.open_child_issues}, closed={epic.closed_child_issues}")
    return 0


def cmd_features(args: argparse.Namespace) -> int:
    if getattr(args, "local", False):
        # Use local FS for playwright-e2e detection (per #64 heuristic); other flags via GitHub
        from pathlib import Path

        repo_path = Path.cwd()
        report = get_features(args.repo)  # still need repo name + most flags from GH
        pw_enabled = detect_playwright_e2e_local(repo_path)
        for f in report.features:
            if f.name == "playwright-e2e":
                f.enabled = pw_enabled
                f.evidence = "local-fs (playwright.config.* or tests/e2e + dep)"
                break
        report.repo = f"{report.repo} (local)"
    else:
        report = get_features(args.repo)

    if args.json:
        print(json.dumps(report.to_dict()))
        return 0

    print(f"Repo: {report.repo}\n")
    feature_names = {
        "autonomous-mode": "Autonomous Mode",
        "plate-config-root": ".plate Root Config",
        "platform-monitor-workflow": "Platform Monitor Workflow",
        "copilot-plugin-root": "Copilot Plugin (.plugin)",
        "copilot-plugin-source": "Copilot Plugin (plugin)",
        "mcp-manifest-root": "MCP Manifest (.plugin)",
        "mcp-manifest-source": "MCP Manifest (plugin)",
        "baseline-agents-catalog": "Baseline Agents Catalog",
        "current-md": "CURRENT.md",
        "playwright-e2e": "Playwright E2E Testing",
    }
    
    for feature in report.features:
        display_name = feature_names.get(feature.name, feature.name)
        status = "✅ ENABLED" if feature.enabled else "⏹️  NOT CONFIGURED"
        print(f"{display_name:.<35} {status}")
    
    if getattr(args, "local", False):
        print("\n(Note: Playwright E2E flag used local filesystem heuristic; run without --local for pure GitHub view.)")
    
    return 0


def cmd_context_list(args: argparse.Namespace) -> int:
    contexts = [route.to_dict() for route in list_context_routes()]
    if args.json:
        print(json.dumps({"contexts": contexts}))
        return 0

    for route in contexts:
        print(f"{route['id']}: {route['concern']}")
        print(f"  First step: {route['first_step']}")
        print(f"  Authority: {', '.join(route['authoritative_artifacts'])}")
    return 0


def cmd_context_show(args: argparse.Namespace) -> int:
    try:
        route = get_context_route(args.context_id)
    except ContextMapError as exc:
        if args.json:
            print(json.dumps({"error": str(exc)}))
        else:
            print(f"Error: {exc}")
        return 1

    if args.json:
        print(json.dumps(route.to_dict()))
        return 0

    print(f"Context: {route.concern} ({route.id})")
    print(f"First step: {route.first_step}")
    print(f"Authoritative artifacts: {', '.join(route.authoritative_artifacts)}")
    print(f"Machine surfaces: {', '.join(route.machine_surfaces)}")
    if route.reference_docs:
        print(f"References: {', '.join(route.reference_docs)}")
    return 0


def cmd_bootstrap(args: argparse.Namespace) -> int:
    adopt: bool | None = None
    if getattr(args, "adopt", False) or getattr(args, "existing_repo", False):
        adopt = True
    elif getattr(args, "greenfield", False):
        adopt = False
    try:
        report = run_bootstrap(
            args.repo,
            apply_mode=args.apply,
            adopt=adopt,
            local_root=getattr(args, "local_root", None),
        )
    except (RuntimeError, GhApiError) as exc:
        if args.json:
            print(json.dumps({"error": str(exc)}))
        else:
            print(f"Error: {exc}")
        return 1
    if args.json:
        print(json.dumps(report.to_dict()))
        return 0

    print(f"Repo: {report.repo}")
    print(f"Mode: {'APPLY' if report.apply_mode else 'DRY-RUN'}")
    print(f"Adoption mode: {report.adoption_mode}")
    print(f"Template source: {report.template_source}")
    for action in report.actions:
        print(f"- {action.name}: {action.state} ({action.detail})")
    if report.next_steps:
        print("Next steps:")
        for step in report.next_steps:
            print(f"  - {step}")
    return 0


def cmd_adopt(args: argparse.Namespace) -> int:
    """Local adoption readiness status (#935 / Epic #633)."""
    from .adoption import assess_adoption_readiness

    report = assess_adoption_readiness(
        getattr(args, "repo_root", ".") or ".",
        include_optional=not bool(getattr(args, "no_optional", False)),
    )
    if args.json:
        print(json.dumps(report))
        return 0
    print(f"Repo root: {report.get('repo_root')}")
    print(f"Core ready: {report.get('core_ready')}")
    print(
        f"Estimated minutes remaining (core): {report.get('estimated_minutes_remaining')} "
        f"(within 30m budget: {report.get('within_30m_budget')})"
    )
    print(f"Checks: {report.get('passed')}/{len(report.get('checks') or [])} passed")
    for c in report.get("checks") or []:
        mark = "ok" if c.get("ok") else "MISSING"
        print(f"  [{mark}] {c.get('id')}: {c.get('title')}")
        if not c.get("ok") and c.get("fix_command"):
            print(f"         fix: {c.get('fix_command')}")
    print(f"Next command: {report.get('next_command')}")
    for step in report.get("next_steps") or []:
        print(f"  - {step}")
    print(f"Guide: {report.get('guide')}")
    return 0 if report.get("ok") else 1


def cmd_self_migrate(args: argparse.Namespace) -> int:
    """Self-migrate dry-run plan, marker merge, or PR plan (#939/#943/#947 / Epic #649)."""
    from .self_migrate import (
        apply_self_migrate_pr,
        plan_marker_merge,
        plan_self_migrate,
        plan_self_migrate_pr,
    )

    if bool(getattr(args, "merge_markers", False)):
        paths = getattr(args, "path", None) or None
        if paths is not None and not isinstance(paths, list):
            paths = [paths]
        report = plan_marker_merge(
            getattr(args, "repo_root", ".") or ".",
            paths=paths,
            upstream_root=getattr(args, "upstream_dir", None),
            apply=bool(getattr(args, "apply_markers", False)),
        )
        if args.json:
            print(json.dumps(report))
            return 0 if report.get("ok") else 1
        print(f"Repo root: {report.get('repo_root')}")
        print(f"Mode: {report.get('mode')}  would_write={report.get('would_write')} written={report.get('written')}")
        for f in report.get("files") or []:
            print(
                f"  - {f.get('path')}: {f.get('action')} changed={f.get('changed')} "
                f"preserved={f.get('preserved_local_sections')}"
            )
        if report.get("errors"):
            for e in report["errors"]:
                print(f"Error: {e}")
        print(f"Next: {report.get('next_command')}")
        print(report.get("note"))
        return 0 if report.get("ok") else 1

    if bool(getattr(args, "pr_plan", False)):
        pr_plan = plan_self_migrate_pr(
            getattr(args, "repo_root", ".") or ".",
            target_version=getattr(args, "target_version", None),
            include_payload=not bool(getattr(args, "no_payload", False)),
            resolve_upstream=bool(getattr(args, "resolve_upstream", False)),
            allow_network=bool(getattr(args, "allow_network", False)),
            base=getattr(args, "base", None) or "release",
            closes=getattr(args, "closes", None),
        )
        apply_report = None
        if bool(getattr(args, "apply_pr", False)):
            apply_report = apply_self_migrate_pr(
                pr_plan,
                dry_run=False,
                allow_high_risk=bool(getattr(args, "allow_high_risk", False)),
                runner=None,  # never auto-run without injectable runner
            )
            report = {"plan": pr_plan, "apply": apply_report}
        else:
            report = pr_plan
        if args.json:
            print(json.dumps(report))
            ok = pr_plan.get("ok") and (
                apply_report is None or apply_report.get("ok") or apply_report.get("dry_run")
            )
            # apply without runner returns ok=False with runner_required — expected surface
            if apply_report and apply_report.get("error") == "runner_required":
                return 0 if pr_plan.get("ok") else 1
            return 0 if (pr_plan.get("ok") and (apply_report is None or apply_report.get("ok"))) else 1
        print(f"PR plan ok={pr_plan.get('ok')} eligible={pr_plan.get('eligible')} risk={pr_plan.get('risk')}")
        print(f"Branch: {pr_plan.get('branch')} base={pr_plan.get('base')}")
        print(f"Title: {pr_plan.get('title')}")
        print(f"Paths: {pr_plan.get('paths')}")
        print(pr_plan.get("note"))
        if apply_report:
            print(f"Apply: ok={apply_report.get('ok')} error={apply_report.get('error')} note={apply_report.get('note')}")
        return 0 if pr_plan.get("ok") else 1

    report = plan_self_migrate(
        getattr(args, "repo_root", ".") or ".",
        target_version=getattr(args, "target_version", None),
        include_payload=not bool(getattr(args, "no_payload", False)),
        resolve_upstream=bool(getattr(args, "resolve_upstream", False)),
        allow_network=bool(getattr(args, "allow_network", False)),
    )
    if args.json:
        print(json.dumps(report))
        return 0
    print(f"Repo root: {report.get('repo_root')}")
    print(f"Installed: {report.get('installed_version')}")
    pin = report.get("pin") or {}
    print(f"Pin: {pin.get('version')} (source={pin.get('source')})")
    print(f"Target: {report.get('target_version')}")
    up = report.get("upstream")
    if up:
        print(
            f"Upstream: version={up.get('version')} source={up.get('source')} "
            f"ok={up.get('ok')} used_network={up.get('used_network')}"
        )
    print(f"Drift: {report.get('drift')}  Risk: {report.get('risk')}")
    comps = report.get("comparisons") or {}
    print(f"Comparisons: {comps}")
    print("Steps:")
    for s in report.get("steps") or []:
        print(f"  - [{s.get('id')}] {s.get('description')}")
    print(f"Next command: {report.get('next_command')}")
    print(report.get("note"))
    return 0 if report.get("ok") else 1


def cmd_config_show(args: argparse.Namespace) -> int:
    report = get_plate_config_report(Path(args.repo_root))
    if args.json:
        print(json.dumps(report.to_dict()))
        return 0

    print(f"Repo root: {report.repo_root}")
    print(f"Path: {report.path}")
    print(f"Present: {report.present}")
    print(f"Valid: {report.valid}")
    print(f"Source: {report.source}")
    if report.file_version:
        print(f"File version: {report.file_version}")
    print(f"Resolved version: {report.resolved_version}")
    print(f"Upgrade available: {report.upgrade_available}")
    if report.enabled_extensions:
        print(f"Enabled extensions: {', '.join(report.enabled_extensions)}")
    if report.errors:
        print(f"Errors: {'; '.join(report.errors)}")
    if report.migration_guidance:
        print("Migration guidance:")
        for step in report.migration_guidance:
            print(f"- {step}")
    print(json.dumps(report.config, indent=2))
    return 0 if report.valid else 1


def cmd_config_validate(args: argparse.Namespace) -> int:
    report = get_plate_config_report(Path(args.repo_root))
    if args.json:
        print(json.dumps(report.to_dict()))
        return 0 if report.valid else 1

    if report.valid:
        print(f".plate is valid ({report.source})")
        return 0
    print(f".plate is invalid: {'; '.join(report.errors)}")
    return 1


def cmd_config_init(args: argparse.Namespace) -> int:
    try:
        report = init_plate_config(Path(args.repo_root), force=bool(args.force))
    except PlateConfigError as exc:
        if args.json:
            print(json.dumps({"path": str(Path(args.repo_root) / '.plate'), "error": str(exc)}))
        else:
            print(str(exc))
        return 1

    if args.json:
        print(json.dumps(report.to_dict()))
        return 0

    print(f"Initialized {report.path}")
    return 0


def cmd_config_upgrade(args: argparse.Namespace) -> int:
    try:
        report = apply_plate_config_upgrade(Path(args.repo_root), apply=bool(args.apply))
    except PlateConfigError as exc:
        if args.json:
            print(json.dumps({"path": str(Path(args.repo_root) / ".plate"), "error": str(exc)}))
        else:
            print(str(exc))
        return 1

    if args.json:
        print(json.dumps(report.to_dict()))
        return 0

    print(f"Path: {report.path}")
    print(f"Previous version: {report.previous_version}")
    print(f"Current version: {report.current_version}")
    print(f"Changed: {report.changed}")
    print(f"Applied: {report.applied}")
    if report.migration_guidance:
        print("Migration guidance:")
        for step in report.migration_guidance:
            print(f"- {step}")
    return 0


def cmd_pr_babysit(args: argparse.Namespace) -> int:
    if args.watch:
        import time

        try:
            while True:
                report = babysit_pr(
                    pr_number=args.pr_number,
                    repo=args.repo,
                    agent_logins=args.agents,
                    act=args.act,
                    branch_update_strategy=args.branch_update_strategy,
                    pr_review_scope=getattr(args, "scope", None),
                )
                if args.json:
                    print(json.dumps(report.to_dict()))
                else:
                    print(f"Repo: {report.repo} | PR #{report.pr_number}")
                    print(
                        f"Detected threads: {report.detected_threads}, actionable: {report.actionable_threads}, "
                        f"scope: {report.pr_review_scope}, "
                        f"trigger posted: {'yes' if report.trigger_comment_posted else 'no'}"
                    )
                    if report.trigger_comment_url:
                        print(f"Trigger comment: {report.trigger_comment_url}")
                    if report.out_of_sync:
                        print(f"Base branch sync: OUT OF SYNC ({report.merge_state})")
                        if report.merge_trigger_posted:
                            print(f"Merge trigger posted: {report.merge_trigger_url}")
                    print(f"Sleeping {args.interval}s...\n")
                time.sleep(args.interval)
        except KeyboardInterrupt:
            return 0

    report = babysit_pr(
        pr_number=args.pr_number,
        repo=args.repo,
        agent_logins=args.agents,
        act=args.act,
        branch_update_strategy=args.branch_update_strategy,
        pr_review_scope=getattr(args, "scope", None),
    )
    if args.json:
        print(json.dumps(report.to_dict()))
        return 0

    print(f"Repo: {report.repo}")
    print(f"PR: #{report.pr_number}")
    print(f"Detected threads: {report.detected_threads}")
    print(f"Actionable review threads: {report.actionable_threads} (scope={report.pr_review_scope})")
    if report.threads_with_suggestions:
        print(f"Threads with ```suggestion``` blocks: {report.threads_with_suggestions}")
    if report.high_risk_suggestion_threads:
        print(f"High-risk path suggestions (do not auto-apply): {report.high_risk_suggestion_threads}")
    if report.auto_resolved_threads:
        print(f"Auto-resolved outdated threads: {report.auto_resolved_threads}")
        if report.auto_resolved_thread_ids:
            for tid in report.auto_resolved_thread_ids:
                print(f"  - {tid}")
    if report.auto_resolve_errors:
        print(f"Auto-resolve errors: {len(report.auto_resolve_errors)}")
        for err in report.auto_resolve_errors:
            print(f"  - {err}")
    if report.trigger_comment_posted:
        print("Babysit trigger posted.")
        if report.trigger_comment_url:
            print(f"Trigger comment: {report.trigger_comment_url}")
    else:
        print("No new babysit trigger posted.")

    # Base branch sync status
    if report.out_of_sync:
        print(f"\nBase branch sync: OUT OF SYNC ({report.merge_state})")
        if report.merge_trigger_posted:
            print("Merge trigger posted.")
            if report.merge_trigger_url:
                print(f"Merge trigger comment: {report.merge_trigger_url}")
        elif report.local_rebase_performed:
            status = "success" if report.local_rebase_success else ("conflict" if report.local_rebase_conflict else "error")
            print(f"Local rebase performed: {status}")
            if report.local_rebase_error:
                print(f"  Error: {report.local_rebase_error}")
        else:
            print("No merge trigger posted (strategy or duplicate).")
    else:
        print(f"\nBase branch sync: UP TO DATE ({report.merge_state})")

    return 0


def cmd_pr_health(args: argparse.Namespace) -> int:
    result = get_pr_merge_gates(
        pr_number=args.pr_number,
        repo=args.repo,
    )
    if args.json:
        print(json.dumps(result))
        return 0

    print(f"Repo: {result['repo']}")
    print(f"PR: #{result['pr_number']}")
    print(f"Merge state: {result.get('merge_state')}")
    print(f"Out of sync: {result.get('out_of_sync')}")
    print(f"Unresolved review threads: {result.get('unresolved_review_threads')}")
    print(f"Actionable agent threads: {result.get('actionable_agent_threads')}")
    if result.get('note'):
        print(f"Note: {result['note']}")
    return 0


def cmd_release_status(args: argparse.Namespace) -> int:
    from pathlib import Path

    releases_dir = Path(args.releases_dir) if getattr(args, "releases_dir", None) else None
    report = get_release_status(args.repo, releases_dir=releases_dir)
    if args.json:
        print(json.dumps(report.to_dict()))
        return 0

    print(f"Repo: {report.repo}")
    print(f"Release branch: {'EXISTS' if report.release_branch_exists else 'MISSING'}")
    if getattr(report, "release_track_branches", None):
        print(f"Release branches: {report.release_track_branches}")
    if getattr(report, "release_branch_mode", None):
        print(f"Release branch mode: {report.release_branch_mode}")
    if getattr(report, "release_branch_reset_target", None):
        print(f"Post-release reset target: {report.release_branch_reset_target}")
    if getattr(report, "warnings", None):
        for warning in report.warnings:
            print(f"WARNING: {warning}")
    print(f"Current version: {report.current_version or '(none)'}")
    print(f"Latest version:  {report.latest_version or '(none)'}")
    print(f"GitHub release exists: {getattr(report, 'github_release_exists', False)}")
    print(f"GitHub release is latest: {getattr(report, 'github_release_is_latest', False)}")
    print(f"GitHub release url: {getattr(report, 'github_release_url', None) or '(none)'}")
    if getattr(report, "github_release_tag", None):
        print(f"GitHub release tag: {report.github_release_tag}")
    print(f"Open Release issues: {len(report.open_release_issues)}")
    for ri in report.open_release_issues:
        print(f"  - #{ri['number']}: {ri['title']}")
    if getattr(report, "active_next_release", None):
        nr = report.active_next_release
        print(f"Active Next Release: #{nr['number']}: {nr['title']} ({nr.get('html_url', '')})")
    if getattr(report, "linked_epics", None):
        print(f"Linked Epics (targeting Next Release): {len(report.linked_epics)}")
        for e in report.linked_epics[:5]:
            print(f"  - #{e['number']}: {e.get('title', '')}")
    if getattr(report, "on_hold_epics", None):
        print(f"On-hold Epics (track label but no target link): {len(report.on_hold_epics)}")
        for e in report.on_hold_epics[:5]:
            print(f"  - #{e['number']}: {e.get('title', '')} {e.get('labels', [])}")
    if getattr(report, "release_track_summary", None):
        print(f"Release track summary (open work with labels): {report.release_track_summary}")
    print(f"Pending unreleased fragments: {report.pending_fragment_count}")
    for frag in report.pending_fragments:
        print(f"  - {frag.slug} [{frag.change_type}]: {frag.summary}")
    if report.extension_release_checks:
        print("Extension release checks:")
        for chk in report.extension_release_checks:
            status = "satisfied" if chk.get("satisfied") else "pending" if chk.get("satisfied") is None else "open"
            req = "REQUIRED" if chk.get("required") else "optional"
            print(f"  [{req}] {chk.get('extension_id')}/{chk.get('id')}: {chk.get('description')} ({status})")
    return 0


def cmd_release_cleanup_branches(args: argparse.Namespace) -> int:
    report = cleanup_dead_branches(
        repo=args.repo,
        base_branch=getattr(args, "base", None),
        apply=bool(getattr(args, "apply", False)),
        limit=getattr(args, "limit", None),
    )
    if args.json:
        print(json.dumps(report.to_dict()))
        return 0

    print(f"Repo: {report.repo}")
    print(f"Base branch: {report.base_branch}")
    print(f"Mode: {'APPLY' if report.apply else 'DRY-RUN'}")
    print(f"Scanned branches: {report.scanned_branches}")
    print(f"Candidates: {len(report.candidates)}")
    for branch in report.candidates:
        print(f"  - {branch}")
    if report.skipped_open_pr:
        print(f"Skipped (open PR): {len(report.skipped_open_pr)}")
    if report.skipped_not_merged:
        print(f"Skipped (not merged into {report.base_branch}): {len(report.skipped_not_merged)}")
    if report.apply:
        print(f"Deleted: {len(report.deleted)}")
        for branch in report.deleted:
            print(f"  - {branch}")
    if report.failed:
        print(f"Failed deletions: {len(report.failed)}")
        for item in report.failed:
            print(f"  - {item.get('branch')}: {item.get('error')}")
    for warning in report.warnings:
        print(f"WARNING: {warning}")
    if not report.apply:
        print("Re-run with --apply to delete candidate branches.")
    return 0


def cmd_release_notes(args: argparse.Namespace) -> int:
    from pathlib import Path

    releases_dir = Path(args.releases_dir) if getattr(args, "releases_dir", None) else None
    report = get_release_notes_diff(
        from_version=getattr(args, "from_version", None),
        to_version=getattr(args, "to_version", None),
        releases_dir=releases_dir,
    )
    if args.json:
        print(json.dumps(report.to_dict()))
        return 0

    from_label = report.from_version or "earliest"
    to_label = report.to_version or "latest"
    print(f"PLATE release notes diff: {from_label} → {to_label}")
    print(f"Versions in range: {', '.join(report.releases_found) or '(none)'}")
    print()
    if not report.entries:
        print("No entries found in the specified range.")
        return 0

    current_version = None
    for entry in report.entries:
        v = entry.get("version", "")
        if v != current_version:
            current_version = v
            print(f"## v{v}")
            print()
        ct = entry.get("change_type", "")
        surface = entry.get("surface", "")
        mi = entry.get("migration_impact", "")
        print(f"  [{ct}] {surface}")
        if mi:
            print(f"    Migration impact: {mi}")
        mg = entry.get("migration_guidance")
        if mg:
            steps = mg if isinstance(mg, list) else [mg]
            print("    Migration steps:")
            for step in steps:
                print(f"      - {step}")
        print()

    if report.migration_steps:
        print("=== Aggregated migration steps ===")
        for step in report.migration_steps:
            print(f"  - {step}")
    return 0


def cmd_costs(args: argparse.Namespace) -> int:
    from .costs import format_cost_markdown, get_cost_dashboard, get_cost_report

    if getattr(args, "dashboard", False):
        dash = get_cost_dashboard(repo=args.repo, epic_label=getattr(args, "epic_label", None))
        if args.json:
            print(json.dumps(dash))
            return 0
        print(dash.get("markdown") or json.dumps(dash, indent=2))
        return 0

    report = get_cost_report(repo=args.repo, epic_label=getattr(args, "epic_label", None))
    if args.json:
        print(json.dumps(report.to_dict()))
        return 0

    print(f"Cost / usage report for {report.repo}")
    print(f"Total tokens: {report.total_tokens}")
    print(f"Total cost: {report.total_cost}")
    print()
    print(format_cost_markdown(report))
    return 0


def cmd_ledger(args: argparse.Namespace) -> int:
    """Provenance / decision ledger CLI (#647)."""
    if getattr(args, "record", False):
        out = record_decision(
            action_kind=getattr(args, "action_kind", None) or "unknown",
            decision=getattr(args, "decision", None) or "proceed",
            reason=getattr(args, "reason", None) or "",
            sources=(getattr(args, "sources", None) or "").split(",") if getattr(args, "sources", None) else [],
            cost_estimate_tokens=getattr(args, "cost_estimate_tokens", None),
            risk_tolerance=getattr(args, "risk_tolerance", None) or "",
            impact=getattr(args, "impact", None) or "",
            related_issue=getattr(args, "related_issue", None),
            related_pr=getattr(args, "related_pr", None),
            shadow_id=getattr(args, "shadow_id", None),
            checkpoint_id=getattr(args, "checkpoint_id", None),
            actor=getattr(args, "by", None) or "cli-user",
        )
        if args.json:
            print(json.dumps(out))
            return 0
        print(f"recorded {out.get('id')} {out.get('action_kind')} -> {out.get('decision')}")
        return 0
    if getattr(args, "get", None):
        rec = get_decision(args.get)
        if args.json:
            print(json.dumps(rec or {"error": "not found"}))
            return 0 if rec else 1
        if not rec:
            print(f"not found: {args.get}", file=sys.stderr)
            return 1
        print(f"{rec.get('id')} {rec.get('action_kind')} {rec.get('decision')}: {rec.get('reason')}")
        return 0
    if getattr(args, "query", None):
        rows = query_decisions(args.query, limit=int(getattr(args, "limit", 50) or 50))
    elif getattr(args, "summary", False):
        s = ledger_summary(limit=int(getattr(args, "limit", 20) or 20))
        if args.json:
            print(json.dumps(s))
            return 0
        try:
            from .ledger import format_ledger_summary_markdown

            print(format_ledger_summary_markdown(s))
        except Exception:
            print(
                f"ledger entries (recent window): {s.get('count')} "
                f"by_decision={s.get('by_decision')} blocking={s.get('blocking_count')}"
            )
        return 0
    else:
        rows = list_decisions(
            action_kind=getattr(args, "action_kind", None),
            decision=getattr(args, "decision", None),
            related_issue=getattr(args, "related_issue", None),
            limit=int(getattr(args, "limit", 50) or 50),
        )
    if args.json:
        print(json.dumps({"decisions": rows}))
        return 0
    if not rows:
        print("No ledger entries.")
        return 0
    for r in rows:
        print(f"{r.get('id')} [{r.get('decision')}] {r.get('action_kind')}: {r.get('reason')[:80]}")
    return 0


def cmd_feed(args: argparse.Namespace) -> int:
    """Endless Q+Task user feed (#631)."""
    feed = get_user_feed(
        repo=getattr(args, "repo", None),
        limit=int(getattr(args, "limit", 10) or 10),
        include_process=not getattr(args, "no_process", False),
        include_autonomy=not getattr(args, "no_autonomy", False),
    )
    if args.json:
        print(json.dumps(feed))
        return 0
    print(feed.get("markdown") or "")
    counts = feed.get("counts") or {}
    print(
        f"(questions={counts.get('questions')} tasks={counts.get('tasks')} "
        f"returned={counts.get('returned')})"
    )
def cmd_plan(args: argparse.Namespace) -> int:
    """Q&A-driven feature/product planning CLI (#628/#630)."""
    kind = getattr(args, "kind", None) or "feature"
    if getattr(args, "script", False):
        out = get_planning_script(kind)
        if args.json:
            print(json.dumps(out))
            return 0
        print(f"Planning script ({out['kind']}): {out['count']} questions")
        for i, q in enumerate(out["questions"], 1):
            print(f"  {i}. [{q['id']}] {q['prompt']}")
        return 0

    if getattr(args, "list_pending", False) or getattr(args, "feed", False) or getattr(
        args, "actionable", False
    ):
        if getattr(args, "feed", False):
            rows = planning_feed_items(limit=int(getattr(args, "limit", 20) or 20))
            key = "feed"
        elif getattr(args, "actionable", False):
            rows = list_actionable_plans(limit=int(getattr(args, "limit", 20) or 20))
            key = "actionable"
        else:
            rows = list_pending_plans(limit=int(getattr(args, "limit", 20) or 20))
            key = "pending"
        if args.json:
            print(json.dumps({key: rows}))
            return 0
        if not rows:
            print(
                "No pending plans."
                if key == "pending"
                else ("No actionable plans." if key == "actionable" else "Planning feed empty.")
            )
            return 0
        for r in rows:
            print(
                f"{r.get('id')} [{r.get('status') or r.get('item_type')}] "
                f"{r.get('title') or r.get('kind')}"
            )
        return 0

    if getattr(args, "resubmit", None):
        out = resubmit_pending_plan(
            str(args.resubmit),
            title=getattr(args, "title", None),
            body=None,
            note=str(getattr(args, "note", None) or ""),
            resubmitted_by=str(getattr(args, "by", None) or "cli-user"),
        )
        if args.json:
            print(json.dumps(out))
            return 0 if out.get("ok") else 1
        if not out.get("ok"):
            print(out.get("error") or "resubmit failed", file=sys.stderr)
            return 1
        print(f"resubmitted {out.get('id')} v{out.get('version')} [{out.get('status')}]")
        return 0

    if getattr(args, "history", None):
        rows = get_plan_history(
            str(args.history), limit=int(getattr(args, "limit", 20) or 20)
        )
        if args.json:
            print(json.dumps({"history": rows}))
            return 0
        if not rows:
            print("No plan history.")
            return 0
        for r in rows:
            print(f"{r.get('ts')} [{r.get('decision')}] by={r.get('by')} v={r.get('version')}")
        return 0

    if getattr(args, "decide", None):
        out = decide_pending_plan(
            str(args.decide),
            str(getattr(args, "decision", None) or "approve"),
            note=str(getattr(args, "note", None) or ""),
            decided_by=str(getattr(args, "by", None) or "cli-user"),
        )
        if args.json:
            print(json.dumps(out))
            return 0 if out.get("ok") else 1
        if not out.get("ok"):
            print(out.get("error") or "decide failed", file=sys.stderr)
            return 1
        print(f"{out.get('status')}: {out.get('plan', {}).get('id')}")
        for step in out.get("next_steps") or []:
            print(f"  - {step}")
        return 0

    br = getattr(args, "budget_remaining", None)
    if br is not None:
        try:
            br = int(br)
        except (TypeError, ValueError):
            br = None
    use_live = not bool(getattr(args, "no_live_budget", False))

    if getattr(args, "build_file", None):
        path = Path(args.build_file)
        session = json.loads(path.read_text(encoding="utf-8"))
        out = build_plan_from_session(
            session, budget_remaining=br, use_live_budget=use_live
        )
        if args.json:
            print(json.dumps(out))
            return 0 if out.get("ok") else 1
        if not out.get("ok"):
            print(out.get("error") or "build failed", file=sys.stderr)
            return 1
        plan = out["plan"]
        print(plan.get("title"))
        print(plan.get("body") or plan.get("summary_body") or "")
        print(
            f"requires_approval={plan.get('requires_approval')} "
            f"est={out.get('cost_estimate_tokens')} remaining={out.get('budget_remaining')}"
        )
        return 0

    # Interactive: start and optionally walk answers from --answers-file
    start = start_planning_session(
        kind, budget_remaining=br, use_live_budget=use_live
    )
    if start.get("ok") is False:
        if args.json:
            print(json.dumps(start))
            return 1
        print(start.get("error") or "start blocked", file=sys.stderr)
        return 1
    if getattr(args, "answers_file", None):
        answers = json.loads(Path(args.answers_file).read_text(encoding="utf-8"))
        session = start["session"]
        if isinstance(answers, list):
            for a in answers:
                out = apply_planning_answer(session, str(a))
                session = out["session"]
        elif isinstance(answers, dict):
            session = {**session, "answers": answers, "complete": True, "turn": 99}
        out = build_plan_from_session(
            session, budget_remaining=br, use_live_budget=use_live
        )
        if args.json:
            print(json.dumps(out))
            return 0 if out.get("ok") else 1
        if not out.get("ok"):
            print(out.get("error") or "build failed", file=sys.stderr)
            return 1
        plan = out.get("plan") or {}
        print(plan.get("title"))
        print(plan.get("body") or plan.get("summary_body") or "")
        return 0

    if args.json:
        print(json.dumps(start))
        return 0
    nq = start.get("next_question") or {}
    print(
        f"Started {kind} planning session. est={start.get('cost_estimate_tokens')} "
        f"remaining={start.get('budget_remaining')}"
    )
    print(f"Next: [{nq.get('id')}] {nq.get('prompt')}")
    print("Record answers via MCP plate_planning_answer or --answers-file JSON array, then --build-file session.json")
    return 0

def cmd_er_plan(args: argparse.Namespace) -> int:
    """Epic/release Q&A planning CLI (#640/#629)."""
    kind = getattr(args, "kind", None) or "epic"
    if getattr(args, "script", False):
        out = get_er_script(kind)
        if args.json:
            print(json.dumps(out))
            return 0
        print(f"{out['kind']} planning: {out['count']} questions")
        for i, q in enumerate(out["questions"], 1):
            print(f"  {i}. [{q['id']}] {q['prompt']}")
        return 0
    if getattr(args, "list_pending", False) or getattr(args, "feed", False):
        rows = er_planning_feed_items(limit=int(getattr(args, "limit", 20) or 20))
        if not getattr(args, "feed", False):
            rows = [r for r in rows if r.get("item_type") == "er_planning_approval"]
        if args.json:
            print(json.dumps({"items": rows}))
            return 0
        if not rows:
            print("No epic/release planning items.")
            return 0
        for r in rows:
            print(
                f"{r.get('id')} [{r.get('status') or r.get('item_type')}] "
                f"{r.get('title') or r.get('kind')}"
            )
        return 0
    if getattr(args, "resubmit", None):
        out = resubmit_er_plan(
            str(args.resubmit),
            title=getattr(args, "title", None),
            note=str(getattr(args, "note", None) or ""),
            resubmitted_by=str(getattr(args, "by", None) or "cli-user"),
        )
        if args.json:
            print(json.dumps(out))
            return 0 if out.get("ok") else 1
        if not out.get("ok"):
            print(out.get("error") or "resubmit failed", file=sys.stderr)
            return 1
        print(f"resubmitted {out.get('id')} v{out.get('version')} [{out.get('status')}]")
        return 0
    if getattr(args, "history", None):
        from .planning import get_plan_history

        rows = get_plan_history(
            str(args.history), limit=int(getattr(args, "limit", 20) or 20)
        )
        if args.json:
            print(json.dumps({"history": rows}))
            return 0
        if not rows:
            print("No ER plan history.")
            return 0
        for r in rows:
            print(f"{r.get('ts')} [{r.get('decision')}] by={r.get('by')} v={r.get('version')}")
        return 0
    if getattr(args, "decide", None):
        out = decide_er_plan(
            str(args.decide),
            str(getattr(args, "decision", None) or "approve"),
            note=str(getattr(args, "note", None) or ""),
            decided_by=str(getattr(args, "by", None) or "cli-user"),
        )
        if args.json:
            print(json.dumps(out))
            return 0 if out.get("ok") else 1
        if not out.get("ok"):
            print(out.get("error") or "decide failed", file=sys.stderr)
            return 1
        print(f"{out.get('status')}: {out.get('plan', {}).get('id')}")
        for step in out.get("next_steps") or []:
            print(f"  - {step}")
        return 0
    br = getattr(args, "budget_remaining", None)
    if br is not None:
        try:
            br = int(br)
        except (TypeError, ValueError):
            br = None
    use_live = not bool(getattr(args, "no_live_budget", False))

    if getattr(args, "answers_file", None):
        answers = json.loads(Path(args.answers_file).read_text(encoding="utf-8"))
        start = start_er_session(
            kind, budget_remaining=br, use_live_budget=use_live
        )
        if start.get("ok") is False:
            if args.json:
                print(json.dumps(start))
                return 1
            print(start.get("error") or "start blocked", file=sys.stderr)
            return 1
        session = start["session"]
        if isinstance(answers, list):
            for a in answers:
                out = apply_er_answer(session, str(a))
                session = out["session"]
        elif isinstance(answers, dict):
            session = {**session, "answers": answers, "complete": True}
        built = build_er_plan_from_session(
            session, budget_remaining=br, use_live_budget=use_live
        )
        if args.json:
            print(json.dumps(built))
            return 0 if built.get("ok") else 1
        if not built.get("ok"):
            print(built.get("error") or "build failed", file=sys.stderr)
            return 1
        plan = built.get("plan") or {}
        print(plan.get("title"))
        print(plan.get("body") or "")
        return 0
    start = start_er_session(kind, budget_remaining=br, use_live_budget=use_live)
    if start.get("ok") is False:
        if args.json:
            print(json.dumps(start))
            return 1
        print(start.get("error") or "start blocked", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(start))
        return 0
    nq = start.get("next_question") or {}
    print(
        f"Started {kind} planning. est={start.get('cost_estimate_tokens')} "
        f"remaining={start.get('budget_remaining')}"
    )
    print(f"Next: [{nq.get('id')}] {nq.get('prompt')}")
    return 0


def cmd_artifact(args: argparse.Namespace) -> int:
    """Design/Research artifact approval CLI (#632)."""
    br = getattr(args, "budget_remaining", None)
    if br is not None:
        try:
            br = int(br)
        except (TypeError, ValueError):
            br = None
    use_live = not bool(getattr(args, "no_live_budget", False))

    if getattr(args, "propose", False):
        out = propose_artifact(
            kind=getattr(args, "kind", None) or "design",
            title=getattr(args, "title", None) or "Artifact",
            summary=getattr(args, "summary", None) or "",
            content_path=getattr(args, "content_path", None) or "",
            related_issue=getattr(args, "related_issue", None),
            related_epic=getattr(args, "related_epic", None),
            originating_question=getattr(args, "originating_question", None),
            actor=getattr(args, "by", None) or "cli-user",
            budget_remaining=br,
            use_live_budget=use_live,
        )
        if args.json:
            print(json.dumps(out))
            return 0 if out.get("ok") is not False else 1
        if out.get("ok") is False:
            print(out.get("error") or "blocked", file=sys.stderr)
            return 1
        print(
            f"proposed {out.get('id')} [{out.get('kind')}] {out.get('title')} "
            f"est={out.get('cost_estimate_tokens')} remaining={out.get('budget_remaining')}"
        )
        print(out.get("approval_prompt"))
        return 0
    if getattr(args, "decide", None):
        if not getattr(args, "decision", None):
            print("--decision required with --decide", file=sys.stderr)
            return 1
        out = decide_proposal(
            args.decide,
            args.decision,
            decided_by=getattr(args, "by", None) or "cli-user",
            note=getattr(args, "note", None) or "",
            open_checkpoint=bool(getattr(args, "open_checkpoint", False)),
        )
        if args.json:
            print(json.dumps(out))
            return 0 if out.get("ok") else 1
        if not out.get("ok"):
            print(out.get("error") or "failed", file=sys.stderr)
            return 1
        print(f"{out.get('id')} -> {out.get('status')}")
        if out.get("next_prompt"):
            print(out["next_prompt"])
        return 0
    if getattr(args, "resubmit", None):
        out = resubmit_proposal(
            str(args.resubmit),
            summary=getattr(args, "summary", None) or None,
            content_path=getattr(args, "content_path", None) or None,
            title=getattr(args, "title", None) or None,
            actor=getattr(args, "by", None) or "cli-user",
            budget_remaining=br,
            use_live_budget=use_live,
        )
        if args.json:
            print(json.dumps(out))
            return 0 if out.get("ok") else 1
        if not out.get("ok"):
            print(out.get("error") or "failed", file=sys.stderr)
            return 1
        print(
            f"resubmitted {out.get('id')} v{out.get('version')} [{out.get('status')}] "
            f"est={out.get('cost_estimate_tokens')} remaining={out.get('budget_remaining')}"
        )
        return 0
    if getattr(args, "history", None):
        rows = get_proposal_history(str(args.history))
        if args.json:
            print(json.dumps({"history": rows}))
            return 0
        if not rows:
            print("No history.")
            return 0
        for r in rows:
            print(f"{r.get('at')} {r.get('decision')} by={r.get('by')} v{r.get('version')}: {r.get('note')}")
        return 0
    if getattr(args, "get", None):
        rec = get_proposal(args.get)
        if args.json:
            print(json.dumps(rec or {"error": "not found"}))
            return 0 if rec else 1
        if not rec:
            print("not found", file=sys.stderr)
            return 1
        print(f"{rec.get('id')} [{rec.get('status')}] {rec.get('title')}")
        return 0
    if getattr(args, "authoritative", False):
        rows = list_authoritative(kind=getattr(args, "kind", None))
    elif getattr(args, "actionable", False) or (getattr(args, "status", None) == "actionable"):
        rows = list_actionable_proposals(kind=getattr(args, "kind", None))
    else:
        rows = list_proposals(
            status=getattr(args, "status", None) or "pending",
            kind=getattr(args, "kind", None),
        )
    if args.json:
        print(json.dumps({"proposals": rows}))
        return 0
    if not rows:
        print("No proposals.")
        return 0
    for r in rows:
        print(f"{r.get('id')} [{r.get('status')}] {r.get('kind')}: {r.get('title')}")
    return 0

def cmd_collab(args: argparse.Namespace) -> int:
    """Human/agent co-existence checks (#643 / #651)."""
    labels = []
    raw = getattr(args, "labels", None) or ""
    if raw:
        labels = [x.strip() for x in str(raw).split(",") if x.strip()]

    if getattr(args, "claim", False):
        kind = getattr(args, "kind", None) or "path"
        target = getattr(args, "target", None) or ""
        out = claim_ownership(
            kind=kind,
            target=target,
            owner=getattr(args, "owner", None) or "human",
            reason=getattr(args, "reason", None) or "",
            related_issue=getattr(args, "number", None),
        )
        if args.json:
            print(json.dumps(out))
            return 0 if out.get("ok") else 1
        claim = out.get("claim") or {}
        print(f"ok={out.get('ok')} id={claim.get('id')} {claim.get('kind')} {claim.get('target')}")
        return 0 if out.get("ok") else 1

    if getattr(args, "release", None):
        rid = getattr(args, "release", None)
        if rid is True or rid == "":
            out = release_ownership(
                kind=getattr(args, "kind", None),
                target=getattr(args, "target", None),
            )
        else:
            out = release_ownership(str(rid))
        if args.json:
            print(json.dumps(out))
            return 0 if out.get("ok") else 1
        print(f"ok={out.get('ok')} released={out.get('n') or 0}")
        return 0 if out.get("ok") else 1

    if getattr(args, "list_claims", False):
        rows = list_ownership_claims(status=getattr(args, "status", None) or "open", limit=50)
        if args.json:
            print(json.dumps(rows))
            return 0
        for r in rows:
            print(f"{r.get('id')} [{r.get('owner')}] {r.get('kind')} {r.get('target')}")
        return 0

    if getattr(args, "etiquette", False):
        out = branch_etiquette_check(
            getattr(args, "branch", None) or "",
            worktree_root=getattr(args, "worktree_root", None),
            repo_root=getattr(args, "repo_root", None),
        )
        if args.json:
            print(json.dumps(out))
            return 0 if out.get("ok") else 1
        print(f"ok={out.get('ok')} reason={out.get('reason')}")
        return 0 if out.get("ok") else 1

    if getattr(args, "concurrent", False):
        paths = []
        raw_p = getattr(args, "paths", None) or ""
        if raw_p:
            paths = [x.strip() for x in str(raw_p).split(",") if x.strip()]
        out = concurrent_edit_risk(paths)
        if args.json:
            print(json.dumps(out))
            return 0
        print(f"level={out.get('level')} advice={out.get('advice')}")
        return 0

    if getattr(args, "ownership_feed", False):
        rows = ownership_feed_items(limit=10)
        if args.json:
            print(json.dumps(rows))
            return 0
        for r in rows:
            print(f"{r.get('id')} {r.get('title')}")
        return 0

    if getattr(args, "issue_status", False):
        out = collab_status_for_issue(
            {"number": getattr(args, "number", None), "title": getattr(args, "title", "") or "", "labels": labels}
        )
        if args.json:
            print(json.dumps(out))
            return 0
        print(f"driver={out.get('driver')} pause_delegation={out.get('pause_delegation')}")
        return 0
    action = getattr(args, "action", None) or "delegate"
    auth = None
    if getattr(args, "author", None) or getattr(args, "mix", None):
        commits = []
        mix = getattr(args, "mix", None)
        if mix == "mixed":
            commits = [{"author": {"login": "human1"}}, {"author": {"login": "bot[bot]"}}]
        elif mix == "human":
            commits = [{"author": {"login": "human1"}}]
        elif mix == "agent":
            commits = [{"author": {"login": "copilot[bot]"}}]
        auth = analyze_pr_authorship(
            author_login=getattr(args, "author", None),
            commits=commits or None,
        )
    paths = []
    raw_p = getattr(args, "paths", None) or ""
    if raw_p:
        paths = [x.strip() for x in str(raw_p).split(",") if x.strip()]
    out = collab_policy_check(
        action,
        labels=labels,
        authorship=auth,
        paths=paths or None,
        branch=getattr(args, "branch", None) or None,
        worktree_root=getattr(args, "worktree_root", None),
        repo_root=getattr(args, "repo_root", None),
    )
    if auth is not None:
        out["authorship"] = auth.to_dict()
    if args.json:
        print(json.dumps(out))
        return 0 if out.get("allowed") else 1
    print(f"allowed={out.get('allowed')} escalate={out.get('escalate')} reason={out.get('reason')}")
    return 0 if out.get("allowed") else 1


def cmd_task(args: argparse.Namespace) -> int:
    """Create, detect, or close human Task issues (#359/#360)."""
    if getattr(args, "close", None):
        out = close_task_with_signal(
            int(args.close),
            comment=str(getattr(args, "comment", None) or "Task complete."),
            repo=getattr(args, "repo", None),
            dry_run=bool(getattr(args, "dry_run", False)),
        )
        if args.json:
            print(json.dumps(out))
            return 0 if out.get("ok") else 1
        print(f"task close: ok={out.get('ok')} number={out.get('number')}")
        return 0 if out.get("ok") else 1

    if getattr(args, "detect", False) or getattr(args, "signal", None):
        signal = str(getattr(args, "signal", None) or "")
        out = detect_and_create_tasks(
            text=signal or None,
            signals=[signal] if signal else None,
            context=str(getattr(args, "context", None) or ""),
            repo=getattr(args, "repo", None),
            dry_run=not bool(getattr(args, "apply", False)),
            create=bool(getattr(args, "apply", False) or getattr(args, "create", False)),
        )
        if args.json:
            print(json.dumps(out))
            return 0 if out.get("ok") else 1
        blockers = out.get("blockers") or []
        print(f"detected {len(blockers)} human blocker(s); create={out.get('create')} dry_run={out.get('dry_run')}")
        for b in blockers:
            print(f"  - {b.get('class_id')}: {b.get('title')}")
        for c in out.get("created") or []:
            print(f"  created: #{c.get('number')} {c.get('url')}")
        return 0

    if getattr(args, "create", False) or getattr(args, "title", None):
        title = getattr(args, "title", None) or ""
        if not title:
            print("task create requires --title", file=sys.stderr)
            return 2
        out = create_task(
            title,
            human_action=str(getattr(args, "human_action", None) or ""),
            why_agent_cannot=str(getattr(args, "why", None) or ""),
            context=str(getattr(args, "context", None) or ""),
            instructions=str(getattr(args, "instructions", None) or ""),
            done_signal=getattr(args, "done_signal", None),
            related_links=getattr(args, "related", None),
            milestone=getattr(args, "milestone", None),
            epic_milestone_name=getattr(args, "epic_milestone", None),
            repo=getattr(args, "repo", None),
            dry_run=bool(getattr(args, "dry_run", False)),
        )
        if args.json:
            print(json.dumps(out))
            return 0 if out.get("ok") else 1
        if not out.get("ok"):
            print(f"task create failed: {out.get('error')}", file=sys.stderr)
            return 1
        if out.get("dry_run"):
            print(f"dry-run Task: {out.get('title')}")
            print(out.get("body", "")[:500])
            return 0
        print(f"Created Task #{out.get('number')}: {out.get('url')}")
        return 0

    print(
        "Usage: gh plate task --create|--detect|--close "
        "(see --help)",
        file=sys.stderr,
    )
    return 2


def cmd_scheduled_ops(args: argparse.Namespace) -> int:
    """Scheduled autonomous operations catalog (#641)."""
    if getattr(args, "list", False) or not any(
        [
            getattr(args, "run", None),
            getattr(args, "plan", None),
            getattr(args, "runs", False),
            getattr(args, "complete", None),
        ]
    ):
        if getattr(args, "status", False) or (
            not getattr(args, "list", False)
            and not getattr(args, "run", None)
            and not getattr(args, "plan", None)
            and not getattr(args, "runs", False)
            and not getattr(args, "complete", None)
        ):
            st = scheduled_ops_status(
                risk_tolerance=str(getattr(args, "risk_tolerance", None) or "medium")
            )
            if args.json:
                print(json.dumps(st))
                return 0
            print(f"ops={st.get('n_ops')} runnable={len(st.get('runnable_at_tolerance') or [])} gated={len(st.get('gated') or [])}")
            for o in st.get("ops") or []:
                print(f"  {o['id']} [{o['risk_level']}/{o['cadence']}] {o['description'][:70]}")
            return 0
        rows = list_ops()
        if args.json:
            print(json.dumps({"ops": rows}))
            return 0
        for o in rows:
            print(f"{o['id']} [{o['risk_level']}] {o['description'][:80]}")
        return 0

    if getattr(args, "plan", None):
        out = plan_op(str(args.plan), dry_run=not getattr(args, "apply", False))
        if args.json:
            print(json.dumps(out))
            return 0 if out.get("ok") else 1
        pkt = (out.get("packet") or {})
        print(f"plan ok={out.get('ok')} steps={len(pkt.get('steps') or [])}")
        for s in pkt.get("steps") or []:
            print(f"  - {s}")
        return 0 if out.get("ok") else 1

    if getattr(args, "run", None):
        budget_remaining = getattr(args, "budget_remaining", None)
        if budget_remaining is not None:
            try:
                budget_remaining = int(budget_remaining)
            except (TypeError, ValueError):
                budget_remaining = None
        out = run_scheduled_op(
            str(args.run),
            dry_run=not getattr(args, "apply", False),
            risk_tolerance=str(getattr(args, "risk_tolerance", None) or "medium"),
            approved=bool(getattr(args, "approved", False)),
            checkpoint_id=getattr(args, "checkpoint_id", None) or None,
            shadow_ack=getattr(args, "shadow_ack", None) or None,
            note=getattr(args, "note", None) or "",
            budget_remaining=budget_remaining,
            use_live_budget=not bool(getattr(args, "no_live_budget", False)),
        )
        if args.json:
            print(json.dumps(out))
            return 0 if out.get("ok") else 1
        print(
            f"ok={out.get('ok')} status={out.get('status')} blocked={out.get('blocked')} "
            f"est={out.get('cost_estimate_tokens')} budget_remaining={out.get('budget_remaining')} "
            f"shadow_id={out.get('shadow_id')}"
        )
        if out.get("blocked") and out.get("error"):
            print(f"error={out.get('error')}")
        return 0 if out.get("ok") else 1

    if getattr(args, "runs", False):
        rows = list_op_runs(
            op_id=getattr(args, "op", None) or None,
            status=str(getattr(args, "run_status", None) or "all"),
            limit=int(getattr(args, "limit", 50) or 50),
        )
        if args.json:
            print(json.dumps({"runs": rows}))
            return 0
        for r in rows:
            print(f"{r.get('id')} {r.get('op_id')} [{r.get('status')}] dry_run={r.get('dry_run')}")
        return 0

    if getattr(args, "complete", None):
        out = complete_op_run(
            str(args.complete),
            status=str(getattr(args, "complete_status", None) or "done"),
            note=getattr(args, "note", None) or "",
        )
        if args.json:
            print(json.dumps(out))
            return 0 if out.get("ok") else 1
        print(f"complete ok={out.get('ok')}")
        return 0 if out.get("ok") else 1

    return 0


def cmd_feature_media(args: argparse.Namespace) -> int:
    """Per-Feature GIF/video capture + approval (#636)."""
    if getattr(args, "list", False):
        rows = list_feature_media(
            status=str(getattr(args, "status", None) or "all"),
            feature_number=getattr(args, "feature", None),
            limit=int(getattr(args, "limit", 50) or 50),
        )
        if args.json:
            print(json.dumps({"records": rows}))
            return 0
        for r in rows:
            print(
                f"{r.get('id')} [{r.get('status')}] feature=#{r.get('feature_number')} "
                f"test={r.get('test_name')} {r.get('gif_path')}"
            )
        return 0

    if getattr(args, "get", None):
        r = get_feature_media(str(args.get))
        if args.json:
            print(json.dumps({"record": r}))
            return 0 if r else 1
        if not r:
            print("not found")
            return 1
        print(f"{r.get('id')} status={r.get('status')} path={r.get('gif_path')}")
        return 0

    if getattr(args, "register", None):
        out = register_capture(
            str(args.register),
            gif_path=getattr(args, "gif_path", None) or None,
            size_bytes=getattr(args, "size_bytes", None),
            quality=getattr(args, "quality", None) or None,
        )
        if args.json:
            print(json.dumps(out))
            return 0 if out.get("ok") else 1
        print(f"ok={out.get('ok')} status={(out.get('record') or {}).get('status')} exists={out.get('file_exists')}")
        return 0 if out.get("ok") else 1

    if getattr(args, "decide", None):
        out = decide_feature_media(
            str(args.decide),
            str(getattr(args, "decision", None) or "approve"),
            decided_by=str(getattr(args, "decided_by", None) or "human"),
            note=getattr(args, "note", None) or None,
        )
        if args.json:
            print(json.dumps(out))
            return 0 if out.get("ok") else 1
        print(f"ok={out.get('ok')} status={(out.get('record') or {}).get('status')}")
        return 0 if out.get("ok") else 1

    if getattr(args, "skip", None):
        out = skip_feature_media(str(args.skip), note=getattr(args, "note", None) or "")
        if args.json:
            print(json.dumps(out))
            return 0 if out.get("ok") else 1
        print(f"skip ok={out.get('ok')}")
        return 0 if out.get("ok") else 1

    if getattr(args, "attach", None):
        frag = getattr(args, "fragment", None) or ""
        out = attach_to_fragment_file(str(args.attach), frag)
        if args.json:
            print(json.dumps(out))
            return 0 if out.get("ok") else 1
        print(f"attach ok={out.get('ok')} path={out.get('fragment_path')}")
        return 0 if out.get("ok") else 1

    if getattr(args, "feed", False):
        rows = feature_media_feed_items(limit=int(getattr(args, "limit", 10) or 10))
        if args.json:
            print(json.dumps({"items": rows}))
            return 0
        for r in rows:
            print(f"{r.get('id')} {r.get('title')}")
        return 0

    if getattr(args, "estimate_cost", False):
        est = estimate_feature_media_cost(
            phase=str(getattr(args, "phase", None) or "plan"),
            quality=str(getattr(args, "quality", None) or "medium"),
        )
        if args.json:
            print(json.dumps(est))
            return 0
        print(f"est={est.get('estimated_tokens')} phase={est.get('phase')} quality={est.get('quality')}")
        return 0

    # default plan
    br = getattr(args, "budget_remaining", None)
    use_live = not bool(getattr(args, "no_live_budget", False))
    out = plan_feature_media(
        feature_number=getattr(args, "feature", None),
        feature_title=str(getattr(args, "title", None) or ""),
        test_name=getattr(args, "test_name", None) or None,
        caption=getattr(args, "caption", None) or None,
        fragment_slug=getattr(args, "fragment_slug", None) or None,
        quality=str(getattr(args, "quality", None) or "medium"),
        budget_remaining=br,
        use_live_budget=use_live,
    )
    if args.json:
        print(json.dumps(out))
        return 0 if out.get("ok") else 1
    if out.get("blocked"):
        print(
            f"blocked budget est={out.get('cost_estimate_tokens')} "
            f"remaining={out.get('budget_remaining')}"
        )
        return 1
    r = out.get("record") or {}
    print(f"ok={out.get('ok')} id={r.get('id')} test={r.get('test_name')} path={r.get('gif_path')}")
    return 0 if out.get("ok") else 1


def cmd_hybrid(args: argparse.Namespace) -> int:
    """Hybrid / non-code project kinds, artifacts, validation (#650)."""
    base = Path(getattr(args, "base_dir", None) or ".agentic/hybrid")
    root = Path(getattr(args, "repo_root", None) or ".")

    if getattr(args, "list_kinds", False) or getattr(args, "list", False):
        rows = list_project_kinds()
        if args.json:
            print(json.dumps({"kinds": rows}))
            return 0
        for r in rows:
            print(f"{r.get('id')}: {r.get('label')} — {r.get('description')}")
        return 0

    if getattr(args, "list_artifacts", False):
        rows = list_artifact_types()
        if args.json:
            print(json.dumps({"artifact_types": rows}))
            return 0
        for r in rows:
            print(f"{r.get('id')}: {r.get('label')}")
        return 0

    if getattr(args, "list_validation", False):
        rows = list_validation_strategies(kind=getattr(args, "kind", None) or None)
        if args.json:
            print(json.dumps({"validation": rows}))
            return 0
        for r in rows:
            print(f"{r.get('id')}: {r.get('label')} ({r.get('command_hint')})")
        return 0

    if getattr(args, "detect", False):
        out = detect_project_kind(root)
        if args.json:
            print(json.dumps(out))
            return 0
        p = out.get("profile") or {}
        print(f"kind={p.get('kind')} confidence={p.get('confidence')} signals={p.get('detected_signals')}")
        return 0

    if getattr(args, "set_kind", None):
        out = set_project_kind(
            str(args.set_kind),
            base_dir=base,
            note=getattr(args, "note", None) or "",
        )
        if args.json:
            print(json.dumps(out))
            return 0 if out.get("ok") else 1
        print(f"ok={out.get('ok')} kind={(out.get('profile') or {}).get('kind')} {out.get('error') or ''}")
        return 0 if out.get("ok") else 1

    if getattr(args, "show", False) or getattr(args, "profile", False):
        out = load_project_profile(base_dir=base, repo_root=root)
        if args.json:
            print(json.dumps(out))
            return 0 if out.get("ok") else 1
        p = out.get("profile") or {}
        print(f"source={out.get('source')} kind={p.get('kind')} validation={p.get('validation')}")
        return 0 if out.get("ok") else 1

    if getattr(args, "template", None):
        kind = str(args.template)
        out = planning_template_for_kind(kind)
        if args.json:
            print(json.dumps(out))
            return 0 if out.get("ok") else 1
        print(f"kind={out.get('kind')} questions={len(out.get('questions') or [])}")
        return 0 if out.get("ok") else 1

    if getattr(args, "validation_plan", False):
        kind = str(getattr(args, "kind", None) or "software")
        out = feature_validation_plan(
            kind,
            feature_title=str(getattr(args, "title", None) or ""),
        )
        if args.json:
            print(json.dumps(out))
            return 0 if out.get("ok") else 1
        print(f"kind={out.get('kind')} steps={len(out.get('steps') or [])}")
        for s in out.get("steps") or []:
            print(f"  - {s.get('id')}: {s.get('command_hint')}")
        return 0 if out.get("ok") else 1

    if getattr(args, "contract", None):
        c = get_kind_contract(str(args.contract))
        if args.json:
            print(json.dumps({"contract": c, "ok": c is not None}))
            return 0 if c else 1
        if not c:
            print("unknown kind")
            return 1
        print(f"{c.get('kind')}: {c.get('label')}")
        return 0

    if getattr(args, "feed", False):
        rows = hybrid_feed_items(base_dir=base, repo_root=root)
        if args.json:
            print(json.dumps({"items": rows}))
            return 0
        for r in rows:
            print(f"{r.get('id')} {r.get('title')}")
        return 0

    # default: show profile
    out = load_project_profile(base_dir=base, repo_root=root)
    if args.json:
        print(json.dumps(out))
        return 0 if out.get("ok") else 1
    p = out.get("profile") or {}
    print(f"source={out.get('source')} kind={p.get('kind')} confidence={p.get('confidence')}")
    return 0 if out.get("ok") else 1


def cmd_packaging(args: argparse.Namespace) -> int:
    """Marketplace packaging with media + adoption proof (#652)."""
    from .release import collect_fragments

    releases_dir = Path(getattr(args, "releases_dir", None) or ".agentic/releases")
    base = Path(getattr(args, "base_dir", None) or ".agentic/packaging")

    if getattr(args, "list", False):
        rows = list_packages(
            base_dir=base,
            status=str(getattr(args, "status", None) or "all"),
            limit=int(getattr(args, "limit", 20) or 20),
        )
        if args.json:
            print(json.dumps({"packages": rows}))
            return 0
        for p in rows:
            print(f"{p.get('id')} v{p.get('version')} [{p.get('status')}]")
        return 0

    if getattr(args, "get", None):
        p = get_package(str(args.get), base_dir=base)
        if args.json:
            print(json.dumps({"package": p}))
            return 0 if p else 1
        if not p:
            print("not found")
            return 1
        print(f"{p.get('id')} v{p.get('version')} status={p.get('status')}")
        return 0

    br = getattr(args, "budget_remaining", None)
    if br is not None:
        try:
            br = int(br)
        except (TypeError, ValueError):
            br = None
    use_live = not bool(getattr(args, "no_live_budget", False))

    if getattr(args, "render", None) or getattr(args, "render_id", None):
        pid = getattr(args, "render", None) or getattr(args, "render_id", None)
        p = get_package(str(pid), base_dir=base) if pid and pid is not True else None
        if p is None and getattr(args, "version", None):
            # build ephemeral then render
            frags = collect_fragments(releases_dir)
            built = build_package(
                str(args.version or "unreleased"),
                frags,
                base_dir=base,
                persist=False,
                budget_remaining=br,
                use_live_budget=use_live,
            )
            if not built.get("ok"):
                if args.json:
                    print(json.dumps(built))
                else:
                    print(f"ok=False blocked={built.get('blocked')} {built.get('error')}")
                return 1
            p = built.get("package")
        if not p:
            print("package not found; build first or pass --version for ephemeral render")
            return 1
        md = render_package_markdown(p)
        if args.json:
            print(json.dumps({"markdown": md, "package_id": p.get("id")}))
            return 0
        print(md)
        return 0

    if getattr(args, "decide", None):
        out = decide_package_publish(
            str(args.decide),
            str(getattr(args, "decision", None) or "approve"),
            decided_by=str(getattr(args, "decided_by", None) or "human"),
            note=getattr(args, "note", None) or "",
            base_dir=base,
        )
        if args.json:
            print(json.dumps(out))
            return 0 if out.get("ok") else 1
        print(f"ok={out.get('ok')} status={(out.get('package') or {}).get('status')} {out.get('error') or out.get('note') or ''}")
        return 0 if out.get("ok") else 1

    if getattr(args, "feed", False):
        rows = packaging_feed_items(base_dir=base, limit=int(getattr(args, "limit", 10) or 10))
        if args.json:
            print(json.dumps({"items": rows}))
            return 0
        for r in rows:
            print(f"{r.get('id')} {r.get('title')}")
        return 0

    if getattr(args, "plan", False):
        out = plan_marketplace_package_op(
            getattr(args, "version", None) or None,
            releases_dir=releases_dir,
            budget_remaining=br,
            use_live_budget=use_live,
        )
        if args.json:
            print(json.dumps(out))
            return 0 if out.get("ok") else 1
        prev = out.get("package_preview") or {}
        print(
            f"ok={out.get('ok')} version={out.get('version')} status={prev.get('status')} "
            f"narratives={prev.get('n_narratives')} est={out.get('cost_estimate_tokens')} "
            f"remaining={out.get('budget_remaining')}"
        )
        return 0 if out.get("ok") else 1

    # default: build
    version = str(getattr(args, "version", None) or "unreleased")
    frags = collect_fragments(releases_dir)
    out = build_package(
        version,
        frags,
        base_dir=base,
        require_approved_media=bool(getattr(args, "require_approved_media", False)),
        persist=not bool(getattr(args, "no_persist", False)),
        budget_remaining=br,
        use_live_budget=use_live,
    )
    if args.json:
        print(json.dumps(out))
        return 0 if out.get("ok") else 1
    p = out.get("package") or {}
    print(
        f"ok={out.get('ok')} id={p.get('id')} v{p.get('version')} status={p.get('status')} "
        f"narratives={len(p.get('narratives') or [])} ready={(p.get('readiness') or {}).get('ready_for_review')} "
        f"est={out.get('cost_estimate_tokens')} remaining={out.get('budget_remaining')}"
    )
    return 0 if out.get("ok") else 1


def cmd_release_media(args: argparse.Namespace) -> int:
    """Release notes GIF/video media helpers (#635)."""
    from .release import collect_fragments

    releases_dir = Path(getattr(args, "releases_dir", None) or ".agentic/releases")
    fragments = collect_fragments(releases_dir)
    media = collect_release_media(fragments)

    if getattr(args, "feed", False):
        rows = media_feed_items(media)
        if args.json:
            print(json.dumps({"items": rows}))
            return 0
        for r in rows:
            print(f"{r.get('id')} {r.get('title')}")
        return 0

    if getattr(args, "decide", False):
        out = decide_media_item(
            media,
            index=getattr(args, "index", None),
            path=getattr(args, "path", None) or None,
            url=getattr(args, "url", None) or None,
            decision=str(getattr(args, "decision", None) or "approve"),
        )
        if args.json:
            print(json.dumps(out))
            return 0 if out.get("ok") else 1
        print(f"ok={out.get('ok')} matched={out.get('matched')} status={out.get('status')}")
        print("Note: decide updates an in-memory list; persist by editing fragment media.approval_status.")
        return 0 if out.get("ok") else 1

    if getattr(args, "render", False):
        only = bool(getattr(args, "approved_only", False))
        md = render_media_markdown(media, only_approved=only)
        if args.json:
            print(json.dumps({"markdown": md, "n": len(media)}))
            return 0
        print(md or "(no media)")
        return 0

    if getattr(args, "validate_paths", False):
        out = validate_media_paths(media, repo_root=Path("."))
        if args.json:
            print(json.dumps(out))
            return 0 if out.get("ok") else 1
        print(f"ok={out.get('ok')} missing={out.get('missing')}")
        return 0 if out.get("ok") else 1

    # default: manifest / summary
    manifest = build_media_manifest(fragments, version=getattr(args, "version", None))
    if args.json:
        print(json.dumps(manifest))
        return 0
    s = manifest.get("summary") or media_approval_summary(media)
    print(f"media total={s.get('n_total')} pending={s.get('n_pending')} approved={s.get('n_approved')}")
    return 0


def cmd_design_contract(args: argparse.Namespace) -> int:
    """Design validation contracts for Features (#646)."""
    if getattr(args, "list", False):
        rows = list_contracts(
            status=str(getattr(args, "status", None) or "all"),
            feature_number=getattr(args, "feature", None),
            limit=int(getattr(args, "limit", 50) or 50),
        )
        if args.json:
            print(json.dumps({"contracts": rows}))
            return 0
        for c in rows:
            print(f"{c.get('id')} [{c.get('status')}] feature=#{c.get('feature_number')} {c.get('feature_title')}")
        return 0

    if getattr(args, "get", None):
        c = get_contract(str(args.get))
        if args.json:
            print(json.dumps({"contract": c}))
            return 0 if c else 1
        if not c:
            print("not found")
            return 1
        print(f"{c.get('id')} status={c.get('status')} interactions={len(c.get('interaction_criteria') or [])}")
        return 0

    if getattr(args, "decide", None):
        out = decide_contract(
            str(args.decide),
            str(getattr(args, "decision", None) or "approve"),
            decided_by=str(getattr(args, "decided_by", None) or "human"),
            note=getattr(args, "note", None) or None,
        )
        if args.json:
            print(json.dumps(out))
            return 0 if out.get("ok") else 1
        print(f"ok={out.get('ok')} status={(out.get('contract') or {}).get('status')}")
        return 0 if out.get("ok") else 1

    if getattr(args, "validate", None):
        out = validate_contract_readiness(str(args.validate))
        if args.json:
            print(json.dumps(out))
            return 0 if out.get("ready") else 1
        print(f"ready={out.get('ready')} checks={out.get('checks')}")
        return 0 if out.get("ready") else 1

    if getattr(args, "scaffold", None):
        c = get_contract(str(args.scaffold))
        if not c:
            print("not found")
            return 1
        sc = build_failing_test_scaffold(c, language=str(getattr(args, "lang", None) or "python"))
        if args.json:
            print(json.dumps(sc))
            return 0
        print(f"# {sc.get('path_hint')}\n{sc.get('content')}")
        return 0

    if getattr(args, "feed", False):
        rows = contract_feed_items(limit=int(getattr(args, "limit", 10) or 10))
        if args.json:
            print(json.dumps({"items": rows}))
            return 0
        for r in rows:
            print(f"{r.get('id')} {r.get('title')}")
        return 0

    # default propose
    interactions = []
    raw_i = getattr(args, "interactions", None) or ""
    if raw_i:
        interactions = [x.strip() for x in str(raw_i).split(";") if x.strip()]
    visuals = []
    raw_v = getattr(args, "visuals", None) or ""
    if raw_v:
        visuals = [x.strip() for x in str(raw_v).split(";") if x.strip()]
    br = getattr(args, "budget_remaining", None)
    if br is not None:
        try:
            br = int(br)
        except (TypeError, ValueError):
            br = None
    out = propose_contract(
        feature_number=getattr(args, "feature", None),
        feature_title=str(getattr(args, "title", None) or ""),
        visual_specs=visuals or None,
        interaction_criteria=interactions or None,
        has_playwright=bool(getattr(args, "playwright", False)),
        submit_for_approval=not bool(getattr(args, "draft", False)),
        budget_remaining=br,
        use_live_budget=not bool(getattr(args, "no_live_budget", False)),
    )
    if args.json:
        print(json.dumps(out))
        return 0 if out.get("ok") else 1
    c = out.get("contract") or {}
    print(
        f"ok={out.get('ok')} id={c.get('id')} status={c.get('status')} "
        f"scaffold={(out.get('test_scaffold') or {}).get('path_hint')} "
        f"est={out.get('cost_estimate_tokens')} remaining={out.get('budget_remaining')}"
    )
    return 0 if out.get("ok") else 1


def cmd_feature_loop(args: argparse.Namespace) -> int:
    """Autonomous feature implementation loop orchestration (#639)."""
    if getattr(args, "estimate", False):
        out = estimate_feature_cost(
            size=str(getattr(args, "size", None) or "medium"),
            needs_design_validation=bool(getattr(args, "design", False)),
            needs_media=not bool(getattr(args, "no_media", False)),
            e2e=bool(getattr(args, "e2e", False)),
        )
        if args.json:
            print(json.dumps(out))
            return 0
        print(f"estimate tokens={out.get('estimated_tokens')} size={out.get('size')}")
        return 0

    if getattr(args, "list", False):
        rows = list_feature_loops(
            status=str(getattr(args, "status", None) or "active"),
            limit=int(getattr(args, "limit", 50) or 50),
        )
        if args.json:
            print(json.dumps({"runs": rows}))
            return 0
        for r in rows:
            print(
                f"{r.get('id')} [{r.get('stage')}] feature=#{r.get('feature_number')} "
                f"pr={r.get('pr_number')} est={r.get('cost_estimate_tokens')} {r.get('feature_title')}"
            )
        return 0

    if getattr(args, "get", None):
        r = get_feature_loop(str(args.get))
        if args.json:
            print(json.dumps({"run": r}))
            return 0 if r else 1
        if not r:
            print("not found")
            return 1
        print(f"{r.get('id')} stage={r.get('stage')} status={r.get('status')} est={r.get('cost_estimate_tokens')}")
        return 0

    if getattr(args, "advance", None):
        out = advance_feature_loop(
            str(args.advance),
            pr_number=getattr(args, "pr", None),
            branch=getattr(args, "branch", None) or None,
            note=getattr(args, "note", None) or None,
            force_skip_checkpoint=bool(getattr(args, "skip_checkpoint", False)),
            skip_media=bool(getattr(args, "skip_media", False)),
        )
        if args.json:
            print(json.dumps(out))
            return 0 if out.get("ok") else 1
        print(
            f"ok={out.get('ok')} advanced={out.get('advanced')} "
            f"{out.get('from_stage')}→{out.get('to_stage') or (out.get('run') or {}).get('stage')}"
        )
        return 0 if out.get("ok") else 1

    if getattr(args, "tick", None):
        out = run_feature_loop_tick(
            str(args.tick),
            dry_run=not getattr(args, "apply", False),
            fetch_gates=bool(getattr(args, "fetch_gates", False)),
            repo=getattr(args, "repo", None),
        )
        if args.json:
            print(json.dumps(out))
            return 0 if out.get("ok") else 1
        pkt = out.get("packet") or {}
        print(f"tick stage={pkt.get('stage')} dry_run={out.get('dry_run')}")
        return 0 if out.get("ok") else 1

    if getattr(args, "cancel", None):
        out = cancel_feature_loop(str(args.cancel), note=getattr(args, "note", None) or "")
        if args.json:
            print(json.dumps(out))
            return 0 if out.get("ok") else 1
        print(f"cancel ok={out.get('ok')}")
        return 0 if out.get("ok") else 1

    if getattr(args, "feed", False):
        rows = feature_loop_feed_items(limit=int(getattr(args, "limit", 10) or 10))
        if args.json:
            print(json.dumps({"items": rows}))
            return 0
        for r in rows:
            print(f"{r.get('id')} {r.get('title')}")
        return 0

    labels = []
    raw = getattr(args, "labels", None) or ""
    if raw:
        labels = [x.strip() for x in str(raw).split(",") if x.strip()]
    out = start_feature_loop(
        feature_number=getattr(args, "feature", None),
        feature_title=str(getattr(args, "title", None) or ""),
        risk=str(getattr(args, "risk", None) or "medium"),
        size=str(getattr(args, "size", None) or "medium"),
        labels=labels or None,
        risk_tolerance=str(getattr(args, "risk_tolerance", None) or "medium"),
        needs_design_validation=bool(getattr(args, "design", False)),
        needs_media_approval=not bool(getattr(args, "no_media", False)),
        e2e=bool(getattr(args, "e2e", False)),
        pr_number=getattr(args, "pr", None),
        branch=getattr(args, "branch", None) or None,
        budget_remaining=getattr(args, "budget_remaining", None),
    )
    if args.json:
        print(json.dumps(out))
        return 0 if out.get("ok") else 1
    run = out.get("run") or {}
    print(
        f"ok={out.get('ok')} id={run.get('id')} stage={run.get('stage')} "
        f"est={run.get('cost_estimate_tokens')} human={run.get('requires_human')}"
    )
    return 0 if out.get("ok") else 1


def cmd_bug_loop(args: argparse.Namespace) -> int:
    """Autonomous bug resolution loop orchestration (#638)."""
    if getattr(args, "list", False):
        rows = list_bug_loops(status=str(getattr(args, "status", None) or "active"), limit=int(getattr(args, "limit", 50) or 50))
        if args.json:
            print(json.dumps({"runs": rows}))
            return 0
        for r in rows:
            print(f"{r.get('id')} [{r.get('stage')}] bug=#{r.get('bug_number')} pr={r.get('pr_number')} {r.get('bug_title')}")
        return 0

    if getattr(args, "get", None):
        r = get_bug_loop(str(args.get))
        if args.json:
            print(json.dumps({"run": r}))
            return 0 if r else 1
        if not r:
            print("not found")
            return 1
        print(f"{r.get('id')} stage={r.get('stage')} status={r.get('status')}")
        return 0

    if getattr(args, "advance", None):
        out = advance_bug_loop(
            str(args.advance),
            pr_number=getattr(args, "pr", None),
            branch=getattr(args, "branch", None) or None,
            note=getattr(args, "note", None) or None,
            force_skip_checkpoint=bool(getattr(args, "skip_checkpoint", False)),
        )
        if args.json:
            print(json.dumps(out))
            return 0 if out.get("ok") else 1
        print(f"ok={out.get('ok')} advanced={out.get('advanced')} {out.get('from_stage')}→{out.get('to_stage') or (out.get('run') or {}).get('stage')}")
        return 0 if out.get("ok") else 1

    if getattr(args, "tick", None):
        out = run_bug_loop_tick(
            str(args.tick),
            dry_run=not getattr(args, "apply", False),
            fetch_gates=bool(getattr(args, "fetch_gates", False)),
            repo=getattr(args, "repo", None),
        )
        if args.json:
            print(json.dumps(out))
            return 0 if out.get("ok") else 1
        pkt = out.get("packet") or {}
        print(f"tick stage={pkt.get('stage')} dry_run={out.get('dry_run')}")
        return 0 if out.get("ok") else 1

    if getattr(args, "cancel", None):
        out = cancel_bug_loop(str(args.cancel), note=getattr(args, "note", None) or "")
        if args.json:
            print(json.dumps(out))
            return 0 if out.get("ok") else 1
        print(f"cancel ok={out.get('ok')}")
        return 0 if out.get("ok") else 1

    if getattr(args, "feed", False):
        rows = bug_loop_feed_items(limit=int(getattr(args, "limit", 10) or 10))
        if args.json:
            print(json.dumps({"items": rows}))
            return 0
        for r in rows:
            print(f"{r.get('id')} {r.get('title')}")
        return 0

    # default start
    labels = []
    raw = getattr(args, "labels", None) or ""
    if raw:
        labels = [x.strip() for x in str(raw).split(",") if x.strip()]
    out = start_bug_loop(
        bug_number=getattr(args, "bug", None),
        bug_title=str(getattr(args, "title", None) or ""),
        risk=str(getattr(args, "risk", None) or "medium"),
        size=str(getattr(args, "size", None) or "medium"),
        labels=labels or None,
        risk_tolerance=str(getattr(args, "risk_tolerance", None) or "medium"),
        pr_number=getattr(args, "pr", None),
        branch=getattr(args, "branch", None) or None,
        budget_remaining=getattr(args, "budget_remaining", None),
        use_live_budget=not bool(getattr(args, "no_live_budget", False)),
    )
    if args.json:
        print(json.dumps(out))
        return 0 if out.get("ok") else 1
    run = out.get("run") or {}
    print(
        f"ok={out.get('ok')} id={run.get('id')} stage={run.get('stage')} "
        f"est={run.get('cost_estimate_tokens')} human={run.get('requires_human')}"
    )
    if out.get("blocked"):
        print(f"blocked: {out.get('error')}")
    return 0 if out.get("ok") else 1


def cmd_stub(args: argparse.Namespace) -> int:
    """Autonomous stub issue authoring + refinement (#637)."""
    if getattr(args, "list", False):
        rows = list_stubs(
            status=str(getattr(args, "status", None) or "all"),
            issue_type=getattr(args, "type", None) or None,
            limit=int(getattr(args, "limit", 50) or 50),
        )
        if args.json:
            print(json.dumps({"drafts": rows}))
            return 0
        for d in rows:
            print(f"{d.get('id')} [{d.get('status')}] {d.get('issue_type')}: {d.get('title')}")
        return 0

    if getattr(args, "refine", None):
        ac = []
        raw_ac = getattr(args, "add_acceptance", None) or ""
        if raw_ac:
            ac = [x.strip() for x in str(raw_ac).split(";") if x.strip()]
        out = refine_stub(
            str(args.refine),
            add_acceptance=ac or None,
            summary_append=getattr(args, "summary", None) or None,
            issue_type=getattr(args, "type", None) or None,
            note=getattr(args, "note", None) or None,
            mark_ready=bool(getattr(args, "ready", False)),
        )
        if args.json:
            print(json.dumps(out))
            return 0 if out.get("ok") else 1
        print(f"ok={out.get('ok')} status={(out.get('draft') or {}).get('status')}")
        return 0 if out.get("ok") else 1

    br = getattr(args, "budget_remaining", None)
    if br is not None:
        try:
            br = int(br)
        except (TypeError, ValueError):
            br = None
    use_live = not bool(getattr(args, "no_live_budget", False))

    if getattr(args, "create", None):
        out = create_stub_issue(
            str(args.create),
            repo=getattr(args, "repo", None),
            dry_run=not getattr(args, "apply", False),
            budget_remaining=br,
            use_live_budget=use_live,
        )
        if args.json:
            print(json.dumps(out))
            return 0 if out.get("ok") else 1
        print(
            f"create ok={out.get('ok')} dry_run={out.get('dry_run')} number={out.get('number')} "
            f"est={out.get('cost_estimate_tokens')} remaining={out.get('budget_remaining')}"
        )
        return 0 if out.get("ok") else 1

    if getattr(args, "feed", False):
        rows = stubs_feed_items(limit=int(getattr(args, "limit", 10) or 10))
        if args.json:
            print(json.dumps({"items": rows}))
            return 0
        for r in rows:
            print(f"{r.get('id')} {r.get('title')}")
        return 0

    # default: author
    intent = getattr(args, "intent", None) or getattr(args, "title", None) or ""
    if getattr(args, "apply", False) and intent:
        out = author_and_create(
            str(intent),
            issue_type=getattr(args, "type", None) or None,
            title=getattr(args, "title", None) or None,
            dry_run=False,
            repo=getattr(args, "repo", None),
            source=str(getattr(args, "source", None) or "qa"),
            budget_remaining=br,
            use_live_budget=use_live,
        )
    else:
        out = author_stub(
            str(intent),
            issue_type=getattr(args, "type", None) or None,
            title=getattr(args, "title", None) or None,
            summary=getattr(args, "summary", None) or None,
            source=str(getattr(args, "source", None) or "qa"),
            parent_epic=getattr(args, "parent_epic", None),
            persist=True,
            budget_remaining=br,
            use_live_budget=use_live,
        )
        if getattr(args, "dry_create", False) and out.get("ok"):
            c = create_stub_issue(
                out["draft"]["id"],
                dry_run=True,
                repo=getattr(args, "repo", None),
                budget_remaining=br,
                use_live_budget=use_live,
            )
            out["create"] = c
    if args.json:
        print(json.dumps(out))
        return 0 if out.get("ok") else 1
    d = out.get("draft") or {}
    print(
        f"ok={out.get('ok')} id={d.get('id')} type={d.get('issue_type')} title={d.get('title')} "
        f"est={out.get('cost_estimate_tokens')} remaining={out.get('budget_remaining')}"
    )
    return 0 if out.get("ok") else 1


def cmd_monitor(args: argparse.Namespace) -> int:
    """Scheduled discussion review + market monitoring (#642)."""
    if getattr(args, "list_proposals", False):
        rows = list_proposals(
            status=str(getattr(args, "status", None) or "pending"),
            source=getattr(args, "source", None) or None,
            limit=int(getattr(args, "limit", 50) or 50),
        )
        if args.json:
            print(json.dumps({"proposals": rows}))
            return 0
        for p in rows:
            print(f"{p.get('id')} [{p.get('score')}] {p.get('proposed_type')}: {p.get('title')}")
        return 0

    if getattr(args, "decide", None):
        out = decide_proposal(
            str(args.decide),
            str(getattr(args, "decision", None) or "approve"),
            created_issue=getattr(args, "created_issue", None),
        )
        if args.json:
            print(json.dumps(out))
            return 0 if out.get("ok") else 1
        print(f"ok={out.get('ok')} status={(out.get('proposal') or {}).get('status')}")
        return 0 if out.get("ok") else 1

    if getattr(args, "feed", False):
        rows = monitoring_feed_items(limit=int(getattr(args, "limit", 10) or 10))
        if args.json:
            print(json.dumps({"items": rows}))
            return 0
        for r in rows:
            print(f"{r.get('id')} {r.get('title')}")
        return 0

    br = getattr(args, "budget_remaining", None)
    if br is not None:
        try:
            br = int(br)
        except (TypeError, ValueError):
            br = None
    use_live = not bool(getattr(args, "no_live_budget", False))

    if getattr(args, "market", False):
        raw = getattr(args, "signals_json", None) or "[]"
        try:
            signals = json.loads(raw) if isinstance(raw, str) else list(raw or [])
        except json.JSONDecodeError:
            # single signal from title
            signals = [{"title": raw, "detail": getattr(args, "detail", "") or ""}]
        if getattr(args, "title", None):
            signals = list(signals) if signals else []
            signals.append(
                {
                    "title": args.title,
                    "detail": getattr(args, "detail", "") or "",
                    "url": getattr(args, "url", "") or "",
                    "impact": getattr(args, "impact", None) or "medium",
                }
            )
        dry = not getattr(args, "apply", False)
        if dry:
            out = run_market_monitor_procedure(
                signals=signals,
                dry_run=True,
                budget_remaining=br,
                use_live_budget=use_live,
            )
        else:
            out = monitor_market_signals(
                signals,
                persist=True,
                budget_remaining=br,
                use_live_budget=use_live,
            )
            out["status"] = "executed" if out.get("ok") else out.get("status") or "blocked"
            out["dry_run"] = False
        if args.json:
            print(json.dumps(out))
            return 0 if out.get("ok") else 1
        print(
            f"market: status={out.get('status')} proposed={out.get('n_proposed')} "
            f"dry_run={out.get('dry_run', dry)} est={out.get('cost_estimate_tokens')} "
            f"remaining={out.get('budget_remaining')}"
        )
        return 0 if out.get("ok") else 1

    # default: discussion review
    dry = not getattr(args, "apply", False)
    discussions = None
    raw_d = getattr(args, "discussions_json", None)
    if raw_d:
        try:
            discussions = json.loads(raw_d)
        except json.JSONDecodeError:
            discussions = None
    if dry:
        out = run_discussion_review_procedure(
            repo=getattr(args, "repo", None),
            discussions=discussions,
            dry_run=True,
            fetch_live=False,
            budget_remaining=br,
            use_live_budget=use_live,
        )
    else:
        out = review_discussions(
            discussions,
            repo=getattr(args, "repo", None),
            persist=True,
            fetch_live=bool(getattr(args, "live", False)),
            budget_remaining=br,
            use_live_budget=use_live,
        )
        out["status"] = "executed" if out.get("ok") else out.get("status") or "blocked"
        out["dry_run"] = False
    if args.json:
        print(json.dumps(out))
        return 0 if out.get("ok") else 1
    print(
        f"discussions: status={out.get('status')} scanned={out.get('n_scanned')} "
        f"proposed={out.get('n_proposed')} dry_run={out.get('dry_run', dry)} "
        f"est={out.get('cost_estimate_tokens')} remaining={out.get('budget_remaining')}"
    )
    return 0 if out.get("ok") else 1


def cmd_fleet(args: argparse.Namespace) -> int:
    """Multi-agent fleet handoffs + budget allocation (#644)."""
    if getattr(args, "roles", False):
        roles = list_fleet_roles()
        if args.json:
            print(json.dumps({"roles": roles}))
            return 0
        for r in roles:
            print(f"{r['id']}: {r['name']} ({r['role']}) share={r.get('default_token_share')}")
        return 0

    if getattr(args, "handoff", False):
        br = getattr(args, "budget_remaining", None)
        if br is not None:
            try:
                br = int(br)
            except (TypeError, ValueError):
                br = None
        out = create_handoff(
            from_agent=str(getattr(args, "from_agent", None) or "orchestrator"),
            to_agent=str(getattr(args, "to_agent", None) or ""),
            task=str(getattr(args, "task", None) or ""),
            budget_tokens=getattr(args, "budget_tokens", None),
            risk=str(getattr(args, "risk", None) or "medium"),
            related_issue=getattr(args, "related_issue", None),
            related_pr=getattr(args, "related_pr", None),
            requires_human=bool(getattr(args, "requires_human", False)),
            budget_remaining=br,
            use_live_budget=not bool(getattr(args, "no_live_budget", False)),
        )
        if args.json:
            print(json.dumps(out))
            return 0 if out.get("ok") else 1
        h = out.get("handoff") or {}
        print(
            f"ok={out.get('ok')} id={h.get('handoff_id')} "
            f"{h.get('from_agent')}→{h.get('to_agent')} "
            f"est={out.get('cost_estimate_tokens')} remaining={out.get('budget_remaining')}"
        )
        return 0 if out.get("ok") else 1

    if getattr(args, "complete", None):
        out = complete_handoff(str(args.complete), notes=str(getattr(args, "note", None) or ""))
        if args.json:
            print(json.dumps(out))
            return 0 if out.get("ok") else 1
        print(f"complete: ok={out.get('ok')} status={(out.get('handoff') or {}).get('status')}")
        return 0 if out.get("ok") else 1

    if getattr(args, "update", None):
        out = update_handoff(
            str(args.update),
            status=getattr(args, "handoff_status", None),
            notes=str(getattr(args, "note", None) or "") or None,
            shadow_ack=getattr(args, "shadow_ack", None) or None,
            approved=bool(getattr(args, "approved", False)),
            checkpoint_id=getattr(args, "checkpoint_id", None) or None,
        )
        if args.json:
            print(json.dumps(out))
            return 0 if out.get("ok") else 1
        print(
            f"update: ok={out.get('ok')} status={(out.get('handoff') or {}).get('status')} "
            f"shadow_id={out.get('shadow_id')}"
        )
        if out.get("blocked") and out.get("error"):
            print(f"error={out.get('error')}")
        return 0 if out.get("ok") else 1

    if getattr(args, "list_handoffs", False):
        rows = list_handoffs(
            status=str(getattr(args, "status", None) or "active"),
            to_agent=getattr(args, "to_agent", None) or None,
            limit=int(getattr(args, "limit", 50) or 50),
        )
        if args.json:
            print(json.dumps({"handoffs": rows}))
            return 0
        for h in rows:
            print(
                f"{h.get('handoff_id')} [{h.get('status')}] "
                f"{h.get('from_agent')}→{h.get('to_agent')}: {h.get('task')}"
            )
        return 0

    if getattr(args, "allocate", False):
        total = int(getattr(args, "budget_tokens", None) or 20000)
        roles = getattr(args, "active_roles", None) or ""
        active = [x.strip() for x in str(roles).split(",") if x.strip()] or None
        out = allocate_fleet_budget(
            total,
            active_roles=active,
            risk_tolerance=str(getattr(args, "risk", None) or "medium"),
        )
        if args.json:
            print(json.dumps(out))
            return 0 if out.get("ok") else 1
        for a in out.get("allocations") or []:
            print(f"{a['agent_id']}: {a['tokens']} tokens (share={a['share']})")
        return 0 if out.get("ok") else 1

    if getattr(args, "plan", None) is not None:
        intent = str(args.plan or "")
        bt = getattr(args, "budget_tokens", None)
        if bt is not None:
            try:
                bt = int(bt)
            except (TypeError, ValueError):
                bt = None
        out = plan_fleet_from_intent(
            intent,
            budget_tokens=bt,
            risk_tolerance=str(getattr(args, "risk", None) or "medium"),
            related_issue=getattr(args, "related_issue", None),
            create=bool(getattr(args, "apply", False)),
            use_live_budget=not bool(getattr(args, "no_live_budget", False)),
        )
        if args.json:
            print(json.dumps(out))
            return 0 if out.get("ok") is not False else 1
        print(
            f"plan ok={out.get('ok')} steps={len(out.get('plan') or [])} "
            f"created={out.get('n_created')} dry_run={out.get('dry_run')} "
            f"remaining={out.get('budget_remaining_tokens')}"
        )
        for s in out.get("plan") or []:
            print(f"  → {s.get('to_agent')}: {s.get('task')[:80]} ({s.get('budget_tokens')} tok)")
        return 0 if out.get("ok") is not False else 1

    if getattr(args, "feed", False):
        rows = handoff_feed_items(limit=int(getattr(args, "limit", 10) or 10))
        if args.json:
            print(json.dumps({"items": rows}))
            return 0
        for r in rows:
            print(f"{r.get('id')} {r.get('title')}")
        return 0

    # default status
    br = getattr(args, "budget_remaining", None)
    if br is None:
        br = getattr(args, "budget_tokens", None)
    if br is not None:
        try:
            br = int(br)
        except (TypeError, ValueError):
            br = None
    st = fleet_status(
        budget_remaining=br,
        use_live_budget=not bool(getattr(args, "no_live_budget", False)),
        risk_tolerance=str(getattr(args, "risk", None) or "medium"),
    )
    if args.json:
        print(json.dumps(st))
        return 0
    print(
        f"fleet: active={st.get('n_active')} human_needed={st.get('human_needed')} "
        f"by_agent={st.get('by_agent')} remaining={st.get('budget_remaining_tokens')}"
    )
    return 0


def cmd_pm(args: argparse.Namespace) -> int:
    """Project Manager orchestrator CLI (#660)."""
    if getattr(args, "team", False):
        team = list_team()
        if args.json:
            print(json.dumps({"team": team}))
            return 0
        for p in team:
            print(f"{p['id']}: {p['name']} ({p['role']}) — {p['style']}")
        return 0
    if getattr(args, "queue", False):
        rows = list_pm_queue(
            repo=getattr(args, "repo", None),
            status=getattr(args, "queue_status", None) or "all",
            limit=int(getattr(args, "limit", 50) or 50),
        )
        if args.json:
            print(json.dumps({"assignments": rows}))
            return 0
        if not rows:
            print("PM queue empty.")
            return 0
        for a in rows:
            print(
                f"{a.get('assignment_id')} [{a.get('status')}] "
                f"{a.get('agent_id')} ← {a.get('work_type')}: {a.get('work_title')}"
            )
        return 0
    if getattr(args, "complete", None):
        out = complete_pm_assignment(
            str(args.complete),
            status=str(getattr(args, "complete_status", None) or "done"),
            note=str(getattr(args, "note", None) or ""),
            repo=getattr(args, "repo", None),
        )
        if args.json:
            print(json.dumps(out))
            return 0 if out.get("ok") else 1
        print(f"complete: ok={out.get('ok')} status={ (out.get('assignment') or {}).get('status') }")
        return 0 if out.get("ok") else 1
    if getattr(args, "tick_loops", False):
        out = tick_pm_loops(
            repo=getattr(args, "repo", None),
            dry_run=not getattr(args, "apply", False),
            fetch_gates=bool(getattr(args, "fetch_loop_gates", False)),
            limit=int(getattr(args, "limit", 20) or 20),
        )
        if args.json:
            print(json.dumps(out))
            return 0
        print(
            f"PM tick_loops: n={out.get('n_ticks')} advanced={out.get('n_advanced')} "
            f"completed={out.get('n_completed')} dry_run={out.get('dry_run')}"
        )
        for t in (out.get("loop_ticks") or [])[:10]:
            print(
                f"  {t.get('loop_kind')} {t.get('loop_run_id')}: "
                f"stage={t.get('stage')} adv={t.get('advanced')} done={t.get('completed_assignment')}"
            )
        return 0
    if getattr(args, "loop", False):
        rep = run_pm_loop(
            repo=getattr(args, "repo", None),
            dry_run=not getattr(args, "apply", False),
            max_cycles=int(getattr(args, "max_cycles", 3) or 3),
            max_assignments=int(getattr(args, "max_assignments", 5) or 5),
        )
        if args.json:
            print(json.dumps(rep))
            return 0
        print(
            f"PM loop: cycles={rep.get('n_cycles')} stop={rep.get('stopped_reason')} "
            f"dry_run={rep.get('dry_run')}"
        )
        for c in rep.get("cycles") or []:
            print(f"  cycle {c.get('cycle')}: {c.get('status')} n={c.get('n_assignments')}")
        return 0
    if getattr(args, "run", False):
        rep = run_pm_cycle(
            repo=getattr(args, "repo", None),
            dry_run=not getattr(args, "apply", False),
            max_assignments=int(getattr(args, "max_assignments", 5) or 5),
            tick_loops=not getattr(args, "no_tick_loops", False),
            fetch_loop_gates=bool(getattr(args, "fetch_loop_gates", False)),
        )
        if args.json:
            print(json.dumps(rep))
            return 0
        print(f"PM cycle: {rep.get('status')} dry_run={rep.get('dry_run')}")
        print(
            f"  assignments={len(rep.get('assignments') or [])} "
            f"blocked={len(rep.get('blocked') or [])} "
            f"loops={len(rep.get('loop_dispatches') or [])} "
            f"ticks={len(rep.get('loop_ticks') or [])}"
        )
        for a in (rep.get("assignments") or [])[:5]:
            print(f"  - {a.get('agent_id')} ← {a.get('work_type')}: {a.get('work_title')}")
        for t in (rep.get("loop_ticks") or [])[:5]:
            print(
                f"  tick {t.get('loop_kind')} {t.get('loop_run_id')}: "
                f"stage={t.get('stage')} done={t.get('completed_assignment')}"
            )
        return 0
    # default status
    st = get_pm_status(getattr(args, "repo", None))
    if args.json:
        print(json.dumps(st))
        return 0
    print(f"PM enabled (autonomy): {st.get('enabled')} risk={st.get('risk_tolerance')}")
    print(f"Budget remaining: {st.get('budget_remaining_tokens')} burn={st.get('burn_rate')}%")
    print(
        f"Team size: {st.get('team_size')} open_checkpoints={st.get('open_checkpoints')} "
        f"queue={st.get('queue_size')} proposed={st.get('proposed')} done={st.get('done')}"
    )
    return 0


def cmd_autonomy(args: argparse.Namespace) -> int:
    """Autonomy status/run/loop surfaces for Epic #470 (host scheduler integration, --loop for persistent budgeted runs)."""
    if getattr(args, "status", False):
        status = get_autonomy_status(args.repo)
        if args.json:
            print(json.dumps(status))
            return 0
        print(f"Enabled: {status.get('enabled')}")
        print(f"Risk tolerance: {status.get('risk_tolerance')}")
        print(f"Autopilot score: {status.get('autopilot_score')}")
        print(f"Burn rate: {status.get('burn_rate', 0)}%")
        if status.get("budget_remaining_tokens") is not None:
            daily = status.get("daily_limit")
            rem = status.get("budget_remaining_tokens")
            if daily is not None:
                print(f"Budget remaining tokens: {rem}/{daily}")
            else:
                print(f"Budget remaining tokens: {rem}")
        # #634/#653 surface fields from durable snapshot (also in --json)
        if status.get("budget_pressure") is not None:
            print(f"Budget pressure: {status.get('budget_pressure')}")
        if status.get("would_pause_next_cycle") is not None or status.get(
            "would_throttle_next_cycle"
        ):
            print(
                f"Next cycle gate: would_pause={status.get('would_pause_next_cycle')} "
                f"would_throttle={status.get('would_throttle_next_cycle')}"
            )
        if status.get("spent_today_durable") is not None:
            print(f"Spent today (durable): {status.get('spent_today_durable')}")
        print(f"Due procedures: {status.get('due_procedures', [])}")
        if status.get("throttled_actions"):
            print(f"Throttled actions: {status.get('throttled_actions')}")
        if status.get("open_human_checkpoints"):
            cps = status.get("open_human_checkpoints") or []
            print(f"Open checkpoints: {len(cps)}")
        print(f"Last cycle: {status.get('last_cycle')}")
        return 0

    if getattr(args, "budget_reset", False):
        from .autonomy import reset_budget_spend

        out = reset_budget_spend(reason=getattr(args, "budget_reset_reason", None) or "cli --budget-reset")
        if args.json:
            print(json.dumps(out))
            return 0 if out.get("ok") else 1
        if not out.get("ok"):
            print(f"Budget reset failed: {out.get('error')}", file=sys.stderr)
            return 1
        print(
            f"Budget spend reset for {out.get('date')}: "
            f"prior_spent_today={out.get('prior_spent_today')} → 0; "
            f"remaining={out.get('remaining_tokens')} pressure={out.get('budget_pressure')}"
        )
        return 0

    if getattr(args, "budget", False):
        from .autonomy import format_budget_snapshot_markdown, get_budget_snapshot

        est = getattr(args, "estimate_tokens", None)
        snap = get_budget_snapshot(args.repo, estimated_tokens=est)
        if args.json:
            print(json.dumps(snap))
            return 0
        print(format_budget_snapshot_markdown(snap), end="")
        return 0

    simulate_kind = getattr(args, "simulate", None)
    if simulate_kind:
        scope: dict = {}
        raw_scope = getattr(args, "scope", None)
        if raw_scope:
            try:
                scope = json.loads(raw_scope)
            except Exception:
                scope = {"raw": raw_scope}
        rep = simulate_autonomy_action(str(simulate_kind), repo=args.repo, scope=scope)
        if args.json:
            print(json.dumps(rep))
            return 0
        print(f"Shadow mode: {rep.get('action_kind')} impact={rep.get('impact')}")
        print(f"  requires_approval={rep.get('requires_approval')} would_execute={rep.get('would_execute')}")
        print(f"  est_tokens={rep.get('estimated_tokens')} est_usd={rep.get('estimated_cost_usd')} duration_s={rep.get('estimated_duration_seconds')}")
        print(f"  shadow_id={rep.get('shadow_id')}")
        for fx in (rep.get("predicted_side_effects") or [])[:5]:
            print(f"  - {fx}")
        if rep.get("approval_reasons"):
            print(f"  reasons: {'; '.join(rep['approval_reasons'])}")
        return 0

    if not getattr(args, "run", False) and not getattr(args, "loop", False):
        print(
            "No --run, --loop, --budget, --budget-reset, or --simulate specified; "
            "execution skipped (use --status or --budget for info only)."
        )
        return 0

    dry_run = getattr(args, "dry_run", False)
    max_steps = getattr(args, "max_steps", None)
    loop = getattr(args, "loop", False)
    run = getattr(args, "run", False)

    if not run and not loop:
        print(
            "Usage: gh plate autonomy --status | --budget [--estimate-tokens N] | "
            "--budget-reset | --simulate ACTION | --run [--dry-run] | --loop [--max-cycles N]",
            file=sys.stderr,
        )
        return 1

    if loop:
        import time
        from .autonomy import AutonomyEngine
        max_cycles = getattr(args, "max_cycles", 3) or 3
        # Create once for persistent in-memory budget/spend across iterations (addresses "recreates each cycle" complaint for budgeted loops)
        engine = AutonomyEngine(repo=args.repo)
        sleep_default = engine.autonomy_config.get("loop", {}).get("default_sleep_seconds", 2) if hasattr(engine, "autonomy_config") else 2
        for i in range(max_cycles):
            if not args.json:
                print(f"Cycle {i+1}/{max_cycles} (dry_run={dry_run})...")
            rep = engine.run_cycle(dry_run=dry_run, max_steps=max_steps)
            if hasattr(rep, "to_dict"):
                rep = rep.to_dict()
            if args.json:
                print(json.dumps(rep))
            else:
                br = rep.get("snapshot", {}).get("cost_report", {}) if isinstance(rep.get("snapshot"), dict) else {}
                print(f"  status={rep.get('status')} budget={rep.get('budget_decision')} actions={len(rep.get('actions_taken', []))} throttled={len(rep.get('throttled', []))}")
            if i < max_cycles - 1:
                sleep_s = getattr(args, "sleep_seconds", None)
                if sleep_s is None:
                    try:
                        acfg = load_plate_config().autonomy or {}
                        sleep_s = int(acfg.get("loop", {}).get("default_sleep_seconds", 2))
                    except Exception:
                        sleep_s = 2
                time.sleep(sleep_s)
        return 0

    rep = run_autonomy_cycle(repo=args.repo, dry_run=dry_run, max_steps=max_steps)
    if args.json:
        print(json.dumps(rep))
        return 0
    print(f"Autonomy cycle: {rep.get('status')}")
    print(f"Budget decision: {rep.get('budget_decision')}")
    print(f"Actions taken: {len(rep.get('actions_taken', []))} (throttled {len(rep.get('throttled', []))})")
    if rep.get('actions_taken'):
        # terse: only first 2 for quiet ops
        for a in rep.get('actions_taken', [])[:2]:
            print(f"  - {a}")
    return 0


def cmd_checkpoint(args: argparse.Namespace) -> int:
    """Unified human checkpoint/approval CLI (#648)."""
    if getattr(args, "get", None):
        rec = get_checkpoint(args.get)
        if args.json:
            print(json.dumps(rec or {"error": "not found"}))
            return 0 if rec else 1
        if not rec:
            print(f"checkpoint not found: {args.get}", file=sys.stderr)
            return 1
        print(f"{rec.get('id')} status={rec.get('status')} impact={rec.get('impact')}")
        print(f"  title: {rec.get('title')}")
        print(f"  reason: {rec.get('reason')}")
        if rec.get("resume_hint"):
            print(f"  resume: {rec.get('resume_hint')}")
        return 0

    if getattr(args, "decide", None):
        if not getattr(args, "decision", None):
            print("--decision required with --decide (approve|revise|reject|cancel)", file=sys.stderr)
            return 1
        out = decide_checkpoint(
            args.decide,
            args.decision,
            decided_by=getattr(args, "decided_by", None) or "cli-user",
            note=getattr(args, "note", "") or "",
        )
        if args.json:
            print(json.dumps(out))
            return 0 if out.get("ok") else 1
        if not out.get("ok"):
            print(out.get("error") or "decide failed", file=sys.stderr)
            return 1
        print(f"decided {out.get('id')} -> {out.get('status')}")
        return 0

    if getattr(args, "create", False):
        title = getattr(args, "title", None) or "Human checkpoint"
        reason = getattr(args, "reason", None) or "Human judgment required"
        eng = AutonomyEngine(repo=getattr(args, "repo", None))
        out = create_checkpoint(
            title,
            reason,
            impact=getattr(args, "impact", None) or "medium",
            action_kind=getattr(args, "action_kind", None) or "",
            shadow_id=getattr(args, "shadow_id", None),
            related_issue=getattr(args, "related_issue", None),
            related_pr=getattr(args, "related_pr", None),
            created_by=getattr(args, "decided_by", None) or "cli-user",
            risk_tolerance=eng.risk_tolerance,
            autonomy_enabled=eng.enabled,
        )
        if args.json:
            print(json.dumps(out))
            return 0
        print(f"created {out.get('id')} status={out.get('status')} impact={out.get('impact')}")
        print(f"  pause_autonomy={out.get('pause_autonomy')} resume_hint={out.get('resume_hint')}")
        return 0

    # default list
    if getattr(args, "open_only", False):
        rows = list_open_checkpoints(limit=50)
    else:
        st = getattr(args, "status", None) or "pending"
        rows = list_checkpoints(status=None if st == "all" else st, limit=50)
    if args.json:
        print(json.dumps({"checkpoints": rows}))
        return 0
    if not rows:
        print("No checkpoints.")
        return 0
    for c in rows:
        print(f"{c.get('id')} [{c.get('status')}] {c.get('impact')}: {c.get('title')}")
    return 0


def cmd_release_cut(args: argparse.Namespace) -> int:
    """First-class gh plate release cut (see #261 Epic and AGENTS.md Release ceremony).

    Uses core implementation (ported from scripts/cut_release.py) for full first-class
    without relying on external script at runtime.
    """
    releases_dir = Path(args.releases_dir) if getattr(args, "releases_dir", None) else None
    version = getattr(args, "version", None)
    version_type = getattr(args, "version_type", None)
    dry_run = getattr(args, "dry_run", False)

    if releases_dir is None:
        releases_dir = Path(".agentic/releases")

    print("Running release cut via plate_core...")
    try:
        rc = core_cut_release(
            version=version,
            releases_dir=releases_dir,
            version_type=version_type,
            dry_run=dry_run,
        )
        return rc
    except Exception as e:
        print(f"Error running cut: {e}")
        return 1


def cmd_release_finalize(args: argparse.Namespace) -> int:
    """First-class finalize for refined ceremony (part of #569 / Epic #306, #591 / #592).
    GitHub Actions owns initial tag on merged Release PR. This surface coordinates:
    - gh release create from release.json (rich notes + simple assets)
    - guarded hard-reset of release branch to tag (opt-in via --apply + pre-checks)
    - ensure next 'Next Release' issue
    - downstream .plate triggers (extensible)
    Core logic lives in plate_core/release.py (create_github_release, perform_guarded_hard_reset,
    ensure_next_release_issue) for reuse by workflow automation in sibling slices.
    See docs/design/release-ceremony-refinement.md, AGENTS.md, and #591/#592.
    """
    version = getattr(args, "version", None) or "vX.Y.Z"
    dry_run = getattr(args, "dry_run", False)
    apply = getattr(args, "apply", False)
    raw_releases = getattr(args, "releases_dir", None)
    releases_dir = Path(raw_releases) if raw_releases else Path(".agentic/releases")
    print(f"Running release finalize for {version} (dry_run={dry_run}, apply={apply})...")
    print("  (Use after the Release PR has merged to main and the tag workflow has run.)")

    # Basic validation + release.json load (reuse existing machinery)
    try:
        from plate_core.release import validate_release_workspace, _load_release
        report = validate_release_workspace(Path("."), releases_dir=releases_dir)
        if report.errors:
            print("Validation errors:", report.errors)
            if not dry_run:
                return 1
        release_data = _load_release(releases_dir, version.lstrip("v")) or {}
    except Exception as e:
        print(f"Could not load release artifacts: {e}")
        release_data = {}

    print("Finalize steps (executed where applicable):")
    print("  1. Tag verified/created by release.yml on merge (see validate_release_workspace).")
    print("  2. gh release create (rich notes from release.json summary+entries; simple assets from v*/assets/ if present).")
    print("  3. Guarded hard-reset (legacy 'release' branch) ONLY if --apply and all guards pass (tag on origin, artifact match).")
    print("  4. Ensure a fresh 'Next Release' issue (label: Release) exists for the standing target.")
    print("  5. Invoke .plate release triggers + extension release_checks (human approval where required).")
    print("  6. gh-plate thin-shim sync/tag/release via publish-gh-plate-extension.yml on plate tag push (#613).")
    if release_data.get("closes_block"):
        print(f"  (Closes block from cut is in release.json; post-merge auto-close of linked issues is now supported via PR body.)")

    # Always attempt create (idempotent + safe). Reset only on explicit --apply.
    from plate_core.release import (
        create_github_release,
        perform_guarded_hard_reset,
        ensure_next_release_issue,
        plan_gh_plate_sync,
    )

    create_info = create_github_release(
        version=version,
        releases_dir=releases_dir,
        dry_run=dry_run,
    )
    print(f"\nGitHub Release: {create_info}")

    reset_info = perform_guarded_hard_reset(
        version=version,
        releases_dir=releases_dir,
        dry_run=dry_run,
        apply=apply,
    )
    print(f"Hard reset: {reset_info}")

    next_info = ensure_next_release_issue()
    print(f"Next Release issue: {next_info}")

    gh_plate_plan = plan_gh_plate_sync(version)
    print(f"gh-plate sync plan (#613): {gh_plate_plan}")
    print("  (Token-scoped workflow owns live git ops on akasper/gh-plate; re-run via Actions workflow_dispatch if repair needed.)")

    if dry_run:
        print("[DRY RUN] No side effects executed (create/reset simulated above).")
        if release_data:
            print("Release data preview keys:", list(release_data.keys())[:5])
        return 0

    print("\nFinalize actions complete (where guards/apply allowed).")
    print("Review the outputs above. Re-run with --apply if you need the hard-reset after confirming state.")
    return 0


def cmd_release_repair(args: argparse.Namespace) -> int:
    """Init/repair standing release tracks + Next Release issue (#320)."""
    from plate_core.release import repair_release_standing_state

    apply = bool(getattr(args, "apply", False))
    dry_run = not apply
    out = repair_release_standing_state(
        repo=getattr(args, "repo", None),
        dry_run=dry_run,
        apply=apply,
    )
    if args.json:
        print(json.dumps(out))
        return 0
    print(f"Release standing repair: health={out.get('diagnosis', {}).get('health')} apply={apply}")
    print(f"  missing_branches={out.get('diagnosis', {}).get('missing_branches')}")
    print(f"  next_release_count={out.get('diagnosis', {}).get('next_release_count')}")
    for a in out.get("actions") or []:
        print(f"  - [{a.get('state')}] {a.get('action')}: {a.get('detail')}")
    if out.get("diagnosis", {}).get("needs_dedupe_next"):
        print("  HUMAN: multiple Next Release issues — keep exactly one.")
    if not apply:
        print("  (dry-run; pass --apply to create missing artifacts)")
    return 0


def cmd_release_target_epic(args: argparse.Namespace) -> int:
    """Validate targeting state and print the manual Next Release link steps for an Epic."""
    epic = getattr(args, "epic", None)
    if not epic:
        print("Usage: gh plate release target-epic <epic-number>")
        return 1
    try:
        epic_number = int(epic)
    except ValueError:
        print(f"Epic must be an integer issue number, got: {epic}")
        return 1

    guidance = get_release_target_epic_guidance(epic_number=epic_number, repo=getattr(args, "repo", None))
    if getattr(args, "json", False):
        print(json.dumps(guidance.to_dict()))
        return 0 if guidance.can_target else 1

    print(f"Repo: {guidance.repo}")
    if guidance.epic:
        epic_info = guidance.epic
        print(f"Epic: #{epic_info['number']}: {epic_info['title']} ({epic_info['html_url']})")
    if guidance.active_next_release:
        next_info = guidance.active_next_release
        print(f"Active Next Release: #{next_info['number']}: {next_info['title']} ({next_info['html_url']})")
    print(guidance.message)
    for step in guidance.manual_steps:
        print(step)
    return 0 if guidance.can_target else 1


def cmd_qanda(args: argparse.Namespace) -> int:
    """Thin CLI surface for Q&A / Curiosity Mode (Epic #139, Features #151/#154).

    For the primary interface (GitHub Copilot CLI) prefer native TUI primitives.
    This gh plate qanda entrypoint is for direct terminal use or scripting.
    """
    from plate_core.mcp.curiosity_tools import (
        ListQuestionsTool,
        GetQuestionTool,
        RecordAnswerTool,
        SynthesizePrioritiesTool,
        CreateBlockingQuestionTool,  # #147 / #151 integration
    )

    repo = getattr(args, "repo", None)
    json_out = getattr(args, "json", False)

    if getattr(args, "list", False) or args.command == "qanda" and not any(
        [getattr(args, "question", None), getattr(args, "synthesize", False), getattr(args, "record", False)]
    ):
        # Default: list + synthesize top priorities
        result = SynthesizePrioritiesTool.execute(repo=repo, max_results=getattr(args, "limit", 5))
        if json_out:
            print(json.dumps(result))
            return 0
        print(f"Repo: {result.get('repo')}")
        print("Prioritized open Questions (Curiosity mode):")
        for i, q in enumerate(result.get("prioritized_questions", []), 1):
            print(f"  {i}. #{q.get('number')}: {q.get('title')}")
            print(f"     {q.get('html_url')}")
        print(f"\n{result.get('rationale', '')}")
        print("Tip: gh plate qanda --question N  |  --record N  (interactive) or --record N --answer 'text'")
        return 0

    if getattr(args, "synthesize", False):
        result = SynthesizePrioritiesTool.execute(repo=repo, max_results=getattr(args, "limit", 5))
        if json_out:
            print(json.dumps(result))
            return 0
        # Human-readable output for non-JSON path (consistent with --list and other commands)
        print(f"Repo: {result.get('repo')}")
        print("Prioritized open Questions (Curiosity mode):")
        for i, q in enumerate(result.get("prioritized_questions", []), 1):
            print(f"  {i}. #{q.get('number')}: {q.get('title')}")
        print(f"\n{result.get('rationale', '')}")
        return 0

    if getattr(args, "question", None):
        qnum = args.question
        result = GetQuestionTool.execute(question_number=qnum, repo=repo)
        if json_out:
            print(json.dumps(result))
            return 0
        print(f"Question #{result.get('number')}: {result.get('title')}")
        print(result.get("html_url", ""))
        if "plate_answer_comments" in result:
            print(f"Detected PLATE-ANSWER blocks: {result.get('answer_count', 0)}")
        print("\n(Use --record to append an answer and trigger contemplation.)")
        return 0

    if getattr(args, "record", None):
        qnum = args.record
        answer_text = getattr(args, "answer", None)
        if not answer_text:
            # Basic interactive fallback TUI for direct gh plate use (#151)
            # (In Copilot CLI primary path, native forms are preferred per Design #144 + guidance)
            print(f"Interactive answer for Question #{qnum} (fallback TUI path).")
            try:
                answer_text = input("Enter your answer (multi-line supported via paste; end with blank line or Ctrl-D):\n").strip()
                if not answer_text:
                    # Simple multi-line read
                    lines = []
                    while True:
                        try:
                            line = input()
                            if not line.strip():
                                break
                            lines.append(line)
                        except EOFError:
                            break
                    answer_text = "\n".join(lines).strip()
            except Exception:
                answer_text = None
            if not answer_text:
                print("No answer provided; aborting record.")
                return 1
        result = RecordAnswerTool.execute(
            question_number=qnum,
            answer_text=answer_text,
            answered_by=getattr(args, "by", "cli-user"),
            repo=repo,
            source="cli-interactive",
        )
        if json_out:
            print(json.dumps(result))
            return 0
        print(f"Answer recorded for #{qnum}: {result.get('status')}")
        if result.get("comment_url"):
            print(f"Comment: {result['comment_url']}")
        print("Next: Contemplation will create follow-ups / unblock if this was a blocking Question (#147/#148).")
        return 0

    # Fallback help
    print("gh plate qanda usage (fallback for direct CLI; prefer native Copilot TUI inside Copilot CLI per Design #144):")
    print("  gh plate qanda --list                    # list + prioritize open Questions")
    print("  gh plate qanda --question 140            # details for one")
    print("  gh plate qanda --record 140              # interactive prompt for answer (basic TUI fallback)")
    print("  gh plate qanda --record 140 --answer 'text'")
    print("  gh plate qanda --synthesize --json")
    print("\nNative Copilot CLI sessions: agent uses host native forms + MCP tools (plate_create_blocking_question for #147 obstacles, record + contemplate for #148 resumption).")
    print("See QANDA_CURIOSITY_GUIDANCE and #151 for full TUI + GIF evidence.")
    return 0


def cmd_agent_delegate(args: argparse.Namespace) -> int:
    try:
        result = delegate_to_agent(args.agent_id, args.task)
    except BaselineCatalogError as exc:
        if args.json:
            print(json.dumps({"error": str(exc)}))
        else:
            print(f"Error: {exc}")
        return 1

    if args.json:
        print(json.dumps(result.to_dict()))
        return 0

    print(f"Delegating to: {result.agent_name} ({result.agent_id})")
    return 0


def cmd_migrate_plan(args: argparse.Namespace) -> int:
    plan = generate_migration_plan()
    if args.json:
        print(json.dumps(plan.__dict__ if hasattr(plan, '__dict__') else str(plan)))
        return 0
    print("Migration Plan (dry-run):")
    print(f"  Risk: {getattr(plan, 'estimated_risk', 'unknown')}")
    for step in getattr(plan, 'steps', []):
        print(f"  - [{step.phase}] {step.id}: {step.description}")
    return 0


def cmd_migrate_apply(args: argparse.Namespace) -> int:
    plan = generate_migration_plan()
    results = apply_migration_plan(plan, dry_run=False)
    if args.json:
        print(json.dumps(results))
        return 0
    print("Migration APPLY results:")
    for r in results:
        print(f"  {r}")
    print("Checkpoint/rollback available via MigrationApplier.")
    return 0


def cmd_spec_audit(args: argparse.Namespace) -> int:
    """#338/#339: audit SPEC.md; optional follow-up issue plan/apply."""
    from .spec_audit import (
        apply_audit_followups,
        audit_spec,
        format_spec_audit_markdown,
        plan_audit_followups,
    )

    report = audit_spec(
        getattr(args, "repo_root", None) or ".",
        releases_dir=getattr(args, "releases_dir", None),
        spec_path=getattr(args, "spec", None),
    )
    data = report.to_dict()
    followups = bool(getattr(args, "followups", False) or getattr(args, "apply_followups", False))
    if followups:
        out = apply_audit_followups(
            report,
            repo=getattr(args, "repo", None),
            apply=bool(getattr(args, "apply_followups", False)),
            max_issues=int(getattr(args, "max_followups", 10) or 10),
        )
        if getattr(args, "json", False):
            print(json.dumps({"audit": data, "followups": out}, indent=2, sort_keys=True))
        else:
            print(format_spec_audit_markdown(report), end="")
            print(f"\nFollow-ups: actionable={out.get('actionable_count')} dry_run={out.get('dry_run')}")
            if out.get("created"):
                for c in out["created"]:
                    print(f"  created #{c.get('number')} {c.get('url')}")
            draft = (out.get("spec_draft") or {}).get("markdown") or ""
            if draft and getattr(args, "show_draft", False):
                print("\n" + draft)
            elif (out.get("spec_draft") or {}).get("items"):
                print(
                    f"SPEC draft items: {(out.get('spec_draft') or {}).get('items')} "
                    f"(use --show-draft; human approval required to edit SPEC.md)"
                )
        return 0 if data.get("ok", False) else 1

    if getattr(args, "json", False):
        print(json.dumps(data, indent=2, sort_keys=True))
    else:
        print(format_spec_audit_markdown(report), end="")
    return 0 if data.get("ok", False) else 1


def cmd_import_payload(args: argparse.Namespace) -> int:
    """#616: plan/apply template payload into a local target checkout."""
    from .import_payload import format_import_payload_report, import_payload

    do_apply = bool(getattr(args, "apply", False))
    ns = None
    if getattr(args, "namespace_scripts", False):
        ns = True
    elif getattr(args, "no_namespace_scripts", False):
        ns = False
    report = import_payload(
        target_dir=getattr(args, "target_dir", None) or ".",
        strategy=getattr(args, "strategy", None) or "safe",
        template_repo=getattr(args, "template_repo", None),
        dry_run=not do_apply,
        apply=do_apply,
        namespace_scripts=ns,
        escape_hatch_dir=getattr(args, "escape_hatch", None),
        escape_hatch_on_conflict=bool(getattr(args, "escape_hatch_on_conflict", False)),
    )
    if getattr(args, "json", False):
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(format_import_payload_report(report), end="")
    return 0 if report.get("ok", True) else 1


def cmd_payload(args: argparse.Namespace) -> int:
    """#621: payload discoverability (list / root / manifest / classify)."""
    from .payload_surface import (
        classify_path,
        list_payload_files,
        resolve_payload_root,
        show_manifest,
    )

    sub = getattr(args, "payload_command", None) or "list"
    if sub == "root":
        out = resolve_payload_root(getattr(args, "template_repo", None))
    elif sub == "manifest":
        out = show_manifest()
    elif sub == "classify":
        path = getattr(args, "path", None)
        if not path:
            print("Error: classify requires a path", file=sys.stderr)
            return 1
        out = classify_path(path, getattr(args, "template_repo", None))
    else:
        out = list_payload_files(
            getattr(args, "template_repo", None),
            include_excluded=bool(getattr(args, "include_excluded", False)),
        )
    if getattr(args, "json", False) or sub in ("manifest", "classify", "root", "list"):
        # default json-friendly for automation; still pretty for humans without --json
        if getattr(args, "json", False):
            print(json.dumps(out, indent=2, sort_keys=True))
        elif sub == "list":
            print(f"Payload root: {out.get('template_root')} ({out.get('source_kind')})")
            print(f"Files: {out.get('count')}")
            for f in (out.get("files") or [])[:50]:
                rule = f.get("path_rule") or {}
                extra = f" rule={rule.get('on_conflict')}" if rule else ""
                print(f"  {f.get('path')} [{f.get('classification')}]{extra}")
            if (out.get("count") or 0) > 50:
                print(f"  ... and {(out.get('count') or 0) - 50} more (use --json)")
        else:
            print(json.dumps(out, indent=2, sort_keys=True))
    return 0 if out.get("ok", True) else 1
    print(f"Task: {result.task_description}")
    print()
    print("Delegation prompt:")
    for line in result.delegation_prompt.splitlines():
        print(f"  {line}")
    print()
    print(f"To use in Copilot: {result.invocation_hints['copilot_plugin']}")
    print(f"To query via CLI:  {result.invocation_hints['gh_plate']}")
    return 0


def cmd_agents_list(args: argparse.Namespace) -> int:
    agents = [agent.to_dict() for agent in list_agents()]
    if args.json:
        print(json.dumps({"agents": agents}))
        return 0

    for agent in agents:
        print(f"{agent['id']}: {agent['name']}")
        print(f"  {agent['description']}")
        print(f"  Skills: {', '.join(agent['primary_skill_ids'])}")
    return 0


def cmd_agent_show(args: argparse.Namespace) -> int:
    agent = get_agent(args.agent_id)
    if args.json:
        print(json.dumps(agent.to_dict()))
        return 0

    print(f"Agent: {agent.name} ({agent.id})")
    print(agent.description)
    print(f"Primary skills: {', '.join(agent.primary_skill_ids)}")
    print(f"Surfaces: {', '.join(agent.surfaces)}")
    if agent.constraints:
        print("Constraints:")
        for constraint in agent.constraints:
            print(f"- {constraint}")
    return 0


def cmd_skills_list(args: argparse.Namespace) -> int:
    skills = [skill.to_dict() for skill in list_skills()]
    if args.json:
        print(json.dumps({"skills": skills}))
        return 0

    for skill in skills:
        print(f"{skill['id']}: {skill['name']}")
        print(f"  {skill['description']}")
        print(f"  Owning agents: {', '.join(skill['owning_agent_ids'])}")
    return 0


def cmd_skill_show(args: argparse.Namespace) -> int:
    skill = get_skill(args.skill_id)
    if args.json:
        print(json.dumps(skill.to_dict()))
        return 0

    print(f"Skill: {skill.name} ({skill.id})")
    print(skill.description)
    print(f"Inputs: {', '.join(skill.inputs)}")
    print(f"Outputs: {', '.join(skill.outputs)}")
    print(f"Owning agents: {', '.join(skill.owning_agent_ids)}")
    if skill.examples:
        print("Examples:")
        for example in skill.examples:
            print(f"- {example}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gh plate", description="PLATE core CLI extension")
    sub = parser.add_subparsers(dest="command", required=True)

    health = sub.add_parser("health", help="Show PLATE health summary")
    health.add_argument("--repo", help="owner/name; defaults to git remote origin")
    health.add_argument(
        "--repo-root",
        dest="repo_root",
        default=".",
        help="Local checkout root for SPEC audit / filesystem signals (#340)",
    )
    health.add_argument(
        "--no-spec-audit",
        action="store_true",
        help="Skip local SPEC audit summary in health output (#340)",
    )
    health.add_argument("--json", action="store_true", help="Output JSON")
    health.set_defaults(func=cmd_health)

    what_next = sub.add_parser(
        "what-next",
        help="Recommend next PLATE process step (budget → open PRs → epics) (#789/#791)",
    )
    what_next.add_argument("--repo", help="owner/name; defaults to git remote origin")
    what_next.add_argument("--agent-type", dest="agent_type", default="general")
    what_next.add_argument("--no-prs", action="store_true", help="Skip open PR scan")
    what_next.add_argument("--no-budget", action="store_true", help="Skip budget snapshot")
    what_next.add_argument(
        "--no-fragments", action="store_true", help="Skip unreleased fragment count"
    )
    what_next.add_argument("--json", action="store_true", help="Output JSON")
    what_next.set_defaults(func=cmd_what_next)

    epic = sub.add_parser("epic", help="Epic-related PLATE commands")
    epic_sub = epic.add_subparsers(dest="epic_command", required=True)
    status = epic_sub.add_parser("status", help="Show Epic status summary")
    status.add_argument("--repo", help="owner/name; defaults to git remote origin")
    status.add_argument("--json", action="store_true", help="Output JSON")
    status.set_defaults(func=cmd_epic_status)

    features = sub.add_parser("features", help="Show optional PLATE feature detection")
    features.add_argument("--repo", help="owner/name; defaults to git remote origin")
    features.add_argument("--json", action="store_true", help="Output JSON")
    features.add_argument("--local", action="store_true", help="Use local filesystem checks for Playwright E2E (config.* + tests/e2e + package.json) per #64 heuristic")
    features.set_defaults(func=cmd_features)

    context = sub.add_parser("context", help="Show canonical PLATE discovery routes")
    context_sub = context.add_subparsers(dest="context_command", required=True)
    context_list = context_sub.add_parser("list", help="List context routes")
    context_list.add_argument("--json", action="store_true", help="Output JSON")
    context_list.set_defaults(func=cmd_context_list)
    context_show = context_sub.add_parser("show", help="Show one context route")
    context_show.add_argument("context_id", help="Context route id")
    context_show.add_argument("--json", action="store_true", help="Output JSON")
    context_show.set_defaults(func=cmd_context_show)

    agents = sub.add_parser("agents", help="Show baseline agent catalog")
    agents_sub = agents.add_subparsers(dest="agents_command", required=True)
    agents_list = agents_sub.add_parser("list", help="List baseline agents")
    agents_list.add_argument("--json", action="store_true", help="Output JSON")
    agents_list.set_defaults(func=cmd_agents_list)
    agent_show = agents_sub.add_parser("show", help="Show baseline agent details")
    agent_show.add_argument("agent_id", help="Baseline agent id")
    agent_show.add_argument("--json", action="store_true", help="Output JSON")
    agent_show.set_defaults(func=cmd_agent_show)
    agent_delegate = agents_sub.add_parser("delegate", help="Delegate a task to a baseline agent")
    agent_delegate.add_argument("agent_id", help="Baseline agent id to delegate to")
    agent_delegate.add_argument("--task", required=True, help="Task description to delegate")
    agent_delegate.add_argument("--json", action="store_true", help="Output JSON")
    agent_delegate.set_defaults(func=cmd_agent_delegate)

    skills = sub.add_parser("skills", help="Show baseline skill catalog")
    skills_sub = skills.add_subparsers(dest="skills_command", required=True)
    skills_list = skills_sub.add_parser("list", help="List baseline skills")
    skills_list.add_argument("--json", action="store_true", help="Output JSON")
    skills_list.set_defaults(func=cmd_skills_list)
    skill_show = skills_sub.add_parser("show", help="Show baseline skill details")
    skill_show.add_argument("skill_id", help="Baseline skill id")
    skill_show.add_argument("--json", action="store_true", help="Output JSON")
    skill_show.set_defaults(func=cmd_skill_show)

    bootstrap = sub.add_parser("bootstrap", help="Plan/apply baseline PLATE bootstrap actions")
    bootstrap.add_argument("--repo", help="owner/name; defaults to git remote origin")
    bootstrap.add_argument("--apply", action="store_true", help="Apply supported actions instead of dry-run planning")
    bootstrap.add_argument(
        "--adopt",
        action="store_true",
        help="Force adoption mode for existing/mature repos (#619)",
    )
    bootstrap.add_argument(
        "--existing-repo",
        action="store_true",
        help="Alias for --adopt",
    )
    bootstrap.add_argument(
        "--greenfield",
        action="store_true",
        help="Force greenfield new-repo bootstrap (disable auto-adopt detect)",
    )
    bootstrap.add_argument(
        "--local-root",
        help="Local checkout path for adoption heuristics (default: cwd)",
    )
    bootstrap.add_argument("--json", action="store_true", help="Output JSON")
    bootstrap.set_defaults(func=cmd_bootstrap)
    # Note: Goals page init (per #266) is included automatically when wiki enabled and page absent (plan in dry-run, apply with --apply). Flag/interactive refinement in future.

    adopt = sub.add_parser(
        "adopt",
        help="Local adoption readiness status for <30m onboarding (#935/#633); status only",
    )
    adopt.add_argument(
        "--repo-root",
        default=".",
        help="Local checkout root (default: current directory)",
    )
    adopt.add_argument(
        "--no-optional",
        action="store_true",
        help="Skip optional SPEC.md/CURRENT.md checks",
    )
    adopt.add_argument("--json", action="store_true", help="Output JSON")
    adopt.set_defaults(func=cmd_adopt)

    self_mig = sub.add_parser(
        "self-migrate",
        help="Pin/payload plan or PLATES-CORE marker merge (#939/#943/#649); dry-run default",
    )
    self_mig.add_argument(
        "--repo-root",
        default=".",
        help="Local checkout root (default: current directory)",
    )
    self_mig.add_argument(
        "--plan",
        action="store_true",
        help="Emit plan (default behavior; accepted for explicit UX)",
    )
    self_mig.add_argument(
        "--target-version",
        help="Optional target plate-core version (default: installed __version__)",
    )
    self_mig.add_argument(
        "--resolve-upstream",
        action="store_true",
        help="Resolve upstream plate-core version for target (#945); offline unless --allow-network",
    )
    self_mig.add_argument(
        "--allow-network",
        action="store_true",
        help="Permit live PyPI fetch when used with --resolve-upstream (default: no network)",
    )
    self_mig.add_argument(
        "--no-payload",
        action="store_true",
        help="Omit import-payload step from the plan",
    )
    self_mig.add_argument(
        "--merge-markers",
        action="store_true",
        help="Plan/apply PLATES-CORE sectional merge vs upstream (#943)",
    )
    self_mig.add_argument(
        "--upstream-dir",
        help="Directory of upstream files for --merge-markers (mirrors relative paths)",
    )
    self_mig.add_argument(
        "--path",
        action="append",
        dest="path",
        help="Relative path to merge (repeatable); default: marker-bearing refresh files",
    )
    self_mig.add_argument(
        "--apply-markers",
        action="store_true",
        help="Write merged marker content (requires --merge-markers); default dry-run",
    )
    self_mig.add_argument(
        "--pr-plan",
        action="store_true",
        help="Emit low-risk migration PR plan (dry-run; no git) (#947)",
    )
    self_mig.add_argument(
        "--apply-pr",
        action="store_true",
        help="Attempt live PR apply (requires --pr-plan; needs injectable runner; blocked without it)",
    )
    self_mig.add_argument(
        "--allow-high-risk",
        action="store_true",
        help="Permit apply of non-low-risk PR plans (still requires runner)",
    )
    self_mig.add_argument(
        "--base",
        default="release",
        help="PR base branch for --pr-plan (default: release)",
    )
    self_mig.add_argument(
        "--closes",
        help="Optional issue ref for PR body (e.g. #947)",
    )
    self_mig.add_argument("--json", action="store_true", help="Output JSON")
    self_mig.set_defaults(func=cmd_self_migrate)

    config = sub.add_parser("config", help="Inspect and initialize local .plate configuration")
    config_sub = config.add_subparsers(dest="config_command", required=True)
    cfg_show = config_sub.add_parser("show", help="Show effective local .plate configuration")
    cfg_show.add_argument("--repo-root", default=".", help="Repository root containing .plate (default: current directory)")
    cfg_show.add_argument("--json", action="store_true", help="Output JSON")
    cfg_show.set_defaults(func=cmd_config_show)
    cfg_validate = config_sub.add_parser("validate", help="Validate local .plate configuration")
    cfg_validate.add_argument("--repo-root", default=".", help="Repository root containing .plate (default: current directory)")
    cfg_validate.add_argument("--json", action="store_true", help="Output JSON")
    cfg_validate.set_defaults(func=cmd_config_validate)
    cfg_init = config_sub.add_parser("init", help="Create a baseline .plate file if missing")
    cfg_init.add_argument("--repo-root", default=".", help="Repository root containing .plate (default: current directory)")
    cfg_init.add_argument(
        "--apply",
        action="store_true",
        help="Accepted for parity with bootstrap flows; config init always writes the file.",
    )
    cfg_init.add_argument("--force", action="store_true", help="Overwrite an existing .plate file")
    cfg_init.add_argument("--json", action="store_true", help="Output JSON")
    cfg_init.set_defaults(func=cmd_config_init)
    cfg_upgrade = config_sub.add_parser("upgrade", help="Upgrade an existing .plate file to the current schema")
    cfg_upgrade.add_argument("--repo-root", default=".", help="Repository root containing .plate (default: current directory)")
    cfg_upgrade.add_argument(
        "--apply",
        action="store_true",
        help="Write the upgraded .plate file back to disk. Without this flag, show the upgrade result only.",
    )
    cfg_upgrade.add_argument("--json", action="store_true", help="Output JSON")
    cfg_upgrade.set_defaults(func=cmd_config_upgrade)

    pr = sub.add_parser("pr", help="PR feedback operations")
    pr_sub = pr.add_subparsers(dest="pr_command", required=True)
    babysit = pr_sub.add_parser(
        "babysit",
        help="Monitor a PR for actionable review feedback and optionally post a local babysit trigger",
    )
    babysit.add_argument("pr_number", type=int, help="Pull request number")
    babysit.add_argument("--repo", help="owner/name; defaults to git remote origin")
    babysit.add_argument(
        "--agents",
        help="Comma-separated GitHub login allowlist (overrides --scope / autonomy.pr_review_scope).",
    )
    babysit.add_argument(
        "--scope",
        choices=["all", "bot-only", "human-only"],
        default=None,
        help="Who counts as actionable (#496): all (default), bot-only, or human-only. Overrides .plate autonomy.pr_review_scope.",
    )
    babysit.add_argument("--act", action="store_true", help="Post a babysit trigger comment when actionable feedback exists")
    babysit.add_argument(
        "--branch-update-strategy",
        choices=["copilot-request", "local-rebase", "none"],
        default="copilot-request",
        help="How to handle out-of-sync base branch: copilot-request (default), local-rebase, or none",
    )
    babysit.add_argument("--watch", action="store_true", help="Continuously monitor the PR")
    babysit.add_argument("--interval", type=int, default=60, help="Polling interval in seconds for --watch mode")
    babysit.add_argument("--json", action="store_true", help="Output JSON")
    babysit.set_defaults(func=cmd_pr_babysit)

    pr_health = pr_sub.add_parser(
        "health",
        help="Get comprehensive merge gates status for a PR (labels, threads, CI, etc.) using the get_pr_merge_gates helper",
    )
    pr_health.add_argument("pr_number", type=int, help="Pull request number")
    pr_health.add_argument("--repo", help="owner/name; defaults to git remote origin")
    pr_health.add_argument("--json", action="store_true", help="Output JSON")
    pr_health.set_defaults(func=cmd_pr_health)

    release = sub.add_parser("release", help="Release status and notes diff (read-only MVP)")
    release_sub = release.add_subparsers(dest="release_command", required=True)
    rel_status = release_sub.add_parser("status", help="Show current release status")
    rel_status.add_argument("--repo", help="owner/name; defaults to git remote origin")
    rel_status.add_argument("--releases-dir", dest="releases_dir", help="Path to releases directory (default: .agentic/releases)")
    rel_status.add_argument("--json", action="store_true", help="Output JSON")
    rel_status.set_defaults(func=cmd_release_status)
    rel_repair = release_sub.add_parser(
        "repair",
        help="Init/repair standing release tracks + Next Release issue (#320)",
    )
    rel_repair.add_argument("--repo", help="owner/name")
    rel_repair.add_argument(
        "--apply",
        action="store_true",
        help="Create missing branches/issues (default dry-run)",
    )
    rel_repair.add_argument("--json", action="store_true")
    rel_repair.set_defaults(func=cmd_release_repair)
    rel_init = release_sub.add_parser(
        "init",
        help="Alias for release repair (#320): ensure standing Next Release state",
    )
    rel_init.add_argument("--repo", help="owner/name")
    rel_init.add_argument("--apply", action="store_true")
    rel_init.add_argument("--json", action="store_true")
    rel_init.set_defaults(func=cmd_release_repair)
    rel_cleanup = release_sub.add_parser(
        "cleanup-branches",
        help="Find and optionally delete dead remote branches (merged + no open PR).",
    )
    rel_cleanup.add_argument("--repo", help="owner/name; defaults to git remote origin")
    rel_cleanup.add_argument(
        "--base",
        help="Base branch to compare merge state against (default: repository default branch).",
    )
    rel_cleanup.add_argument(
        "--apply",
        action="store_true",
        help="Delete candidate branches. Without this flag, command runs in dry-run mode.",
    )
    rel_cleanup.add_argument(
        "--limit",
        type=int,
        help="Optional maximum number of candidate branches to delete/report.",
    )
    rel_cleanup.add_argument("--json", action="store_true", help="Output JSON")
    rel_cleanup.set_defaults(func=cmd_release_cleanup_branches)
    rel_notes = release_sub.add_parser("notes", help="Show release notes diff between versions")
    rel_notes.add_argument("--from", dest="from_version", help="Start version (exclusive)")
    rel_notes.add_argument("--to", dest="to_version", help="End version (inclusive)")
    rel_notes.add_argument("--releases-dir", dest="releases_dir", help="Path to releases directory (default: .agentic/releases)")
    rel_notes.add_argument("--json", action="store_true", help="Output JSON")
    rel_notes.set_defaults(func=cmd_release_notes)

    costs = sub.add_parser("costs", help="Harvest and aggregate USAGE REPORTs for observability/cost tracking (Epic #265)")
    costs.add_argument("--repo", help="owner/name; defaults to git remote origin")
    costs.add_argument("--epic-label", dest="epic_label", help="Filter to reports under a specific Epic: label (e.g. Epic: beta-roadmap)")
    costs.add_argument(
        "--dashboard",
        action="store_true",
        help="Cost+risk dashboard with budgets, burn, drift signals, ranked feed items (#653/#634)",
    )
    costs.add_argument("--json", action="store_true", help="Output JSON")
    costs.set_defaults(func=cmd_costs)

    ledger = sub.add_parser(
        "ledger",
        help="Provenance + decision ledger for autonomous actions (#647): record, list, query, get, summary",
    )
    ledger.add_argument("--json", action="store_true")
    ledger.add_argument("--record", action="store_true", help="Record a decision entry")
    ledger.add_argument("--action-kind", dest="action_kind", help="Action kind for --record or filter")
    ledger.add_argument("--decision", help="Decision value (proceed|throttle|pause|...)")
    ledger.add_argument("--reason", help="Why this decision was made")
    ledger.add_argument("--sources", help="Comma-separated data sources")
    ledger.add_argument("--cost-estimate-tokens", dest="cost_estimate_tokens", type=int)
    ledger.add_argument("--risk-tolerance", dest="risk_tolerance")
    ledger.add_argument("--impact")
    ledger.add_argument("--related-issue", dest="related_issue", type=int)
    ledger.add_argument("--related-pr", dest="related_pr", type=int)
    ledger.add_argument("--shadow-id", dest="shadow_id")
    ledger.add_argument("--checkpoint-id", dest="checkpoint_id")
    ledger.add_argument("--by", default="cli-user")
    ledger.add_argument("--list", action="store_true", help="List recent entries (default)")
    ledger.add_argument("--query", help="Substring search")
    ledger.add_argument("--get", metavar="ID", help="Get one entry")
    ledger.add_argument("--summary", action="store_true", help="Counts by decision")
    ledger.add_argument("--limit", type=int, default=50)
    ledger.set_defaults(func=cmd_ledger)
    feed = sub.add_parser(
        "feed",
        help="Endless ranked feed of open Questions + Tasks for user surfacing (#631)",
    )
    feed.add_argument("--repo", help="owner/name; defaults to git remote origin")
    feed.add_argument("--limit", type=int, default=10, help="Max items (default 10)")
    feed.add_argument("--no-process", action="store_true", help="Omit plate_what_next process item")
    feed.add_argument("--no-autonomy", action="store_true", help="Omit autonomy checkpoints")
    feed.add_argument("--json", action="store_true", help="Output JSON")
    feed.set_defaults(func=cmd_feed)
    plan = sub.add_parser(
        "plan",
        help="Q&A-driven feature (#630) or product (#628) planning: script, start, build, decide, list",
    )
    plan.add_argument("kind", nargs="?", default="feature", choices=["feature", "product"], help="Planning kind")
    plan.add_argument("--script", action="store_true", help="Print ordered questions")
    plan.add_argument("--answers-file", dest="answers_file", help="JSON array of answers to walk session offline")
    plan.add_argument("--build-file", dest="build_file", help="JSON session file to build plan from")
    plan.add_argument("--list-pending", dest="list_pending", action="store_true", help="List pending plan stubs")
    plan.add_argument(
        "--actionable",
        action="store_true",
        help="List pending + revise_requested plans (#630)",
    )
    plan.add_argument("--feed", action="store_true", help="List planning feed items (pending + sessions)")
    plan.add_argument("--decide", metavar="ID", help="Decide on pending plan id")
    plan.add_argument(
        "--resubmit",
        metavar="ID",
        help="Resubmit revise_requested plan for re-approval (#630)",
    )
    plan.add_argument("--history", metavar="ID", help="Show decision history for a plan id")
    plan.add_argument("--title", help="Optional title override for --resubmit")
    plan.add_argument(
        "--decision",
        choices=["approve", "revise", "reject"],
        default="approve",
        help="Decision for --decide (default approve)",
    )
    plan.add_argument("--note", default="", help="Decision note")
    plan.add_argument("--by", default="cli-user", help="Actor for --decide")
    plan.add_argument(
        "--budget-remaining",
        dest="budget_remaining",
        type=int,
        default=None,
        help="Explicit remaining tokens for #634 gate (overrides live hydrate)",
    )
    plan.add_argument(
        "--no-live-budget",
        dest="no_live_budget",
        action="store_true",
        help="Do not hydrate budget from spend.json / .plate",
    )
    plan.add_argument("--limit", type=int, default=20)
    plan.add_argument("--json", action="store_true")
    plan.set_defaults(func=cmd_plan)

    er_plan = sub.add_parser(
        "er-plan",
        help="Q&A epic (#640) or release (#629) planning: script / start / build / decide / feed",
    )
    er_plan.add_argument("kind", nargs="?", default="epic", choices=["epic", "release"])
    er_plan.add_argument("--script", action="store_true")
    er_plan.add_argument("--answers-file", dest="answers_file", help="JSON array of answers")
    er_plan.add_argument("--list-pending", dest="list_pending", action="store_true")
    er_plan.add_argument("--feed", action="store_true", help="Pending ER plans + incomplete sessions")
    er_plan.add_argument("--decide", metavar="ID", help="Decide pending epic/release plan id")
    er_plan.add_argument(
        "--resubmit",
        metavar="ID",
        help="Resubmit revise_requested epic/release plan (#640/#629)",
    )
    er_plan.add_argument("--history", metavar="ID", help="Decision history for ER plan id")
    er_plan.add_argument("--title", help="Optional title override for --resubmit")
    er_plan.add_argument(
        "--decision",
        choices=["approve", "revise", "reject"],
        default="approve",
    )
    er_plan.add_argument("--note", default="")
    er_plan.add_argument("--by", default="cli-user")
    er_plan.add_argument(
        "--budget-remaining",
        dest="budget_remaining",
        type=int,
        default=None,
        help="Explicit remaining tokens for #634 gate (overrides live hydrate)",
    )
    er_plan.add_argument(
        "--no-live-budget",
        dest="no_live_budget",
        action="store_true",
        help="Do not hydrate budget from spend.json / .plate",
    )
    er_plan.add_argument("--limit", type=int, default=20)
    er_plan.add_argument("--json", action="store_true")
    er_plan.set_defaults(func=cmd_er_plan)

    artifact = sub.add_parser(
        "artifact",
        help="Design/Research artifact approval (#632): propose, decide, resubmit, history, list",
    )
    artifact.add_argument("--propose", action="store_true")
    artifact.add_argument("--kind", choices=["design", "research"], default="design")
    artifact.add_argument("--title")
    artifact.add_argument("--summary", default="")
    artifact.add_argument("--content-path", dest="content_path", default="")
    artifact.add_argument("--related-issue", dest="related_issue", type=int)
    artifact.add_argument("--related-epic", dest="related_epic", type=int)
    artifact.add_argument("--originating-question", dest="originating_question", type=int)
    artifact.add_argument("--decide", metavar="ID")
    artifact.add_argument("--decision", choices=["approve", "revise", "reject"])
    artifact.add_argument("--note", default="")
    artifact.add_argument(
        "--open-checkpoint",
        dest="open_checkpoint",
        action="store_true",
        help="On revise, open a #648 checkpoint when related_issue is set",
    )
    artifact.add_argument("--resubmit", metavar="ID", help="Resubmit revised content for re-approval")
    artifact.add_argument("--history", metavar="ID", help="Show decision history for proposal")
    artifact.add_argument("--get", metavar="ID")
    artifact.add_argument("--list", action="store_true")
    artifact.add_argument("--status", default="pending", help="pending|revised|approved|rejected|actionable|all")
    artifact.add_argument("--actionable", action="store_true", help="List pending+revised")
    artifact.add_argument("--authoritative", action="store_true")
    artifact.add_argument("--by", default="cli-user")
    artifact.add_argument(
        "--budget-remaining",
        dest="budget_remaining",
        type=int,
        default=None,
        help="Explicit remaining tokens for #634 gate (overrides live hydrate)",
    )
    artifact.add_argument(
        "--no-live-budget",
        dest="no_live_budget",
        action="store_true",
        help="Do not hydrate budget from spend.json / .plate",
    )
    artifact.add_argument("--json", action="store_true")
    artifact.set_defaults(func=cmd_artifact)

    collab = sub.add_parser(
        "collab",
        help="Human/agent co-existence + ownership etiquette (#643/#651)",
    )
    collab.add_argument("--action", default="delegate", help="Action to gate: delegate|push_branch|force_push|auto_merge|...")
    collab.add_argument("--labels", default="", help="Comma-separated labels (include driver:human etc.)")
    collab.add_argument("--author", default="", help="PR author login")
    collab.add_argument("--mix", choices=["human", "agent", "mixed"], help="Simulated authorship mix for checks")
    collab.add_argument("--issue-status", action="store_true", help="Summarize driver state for labels")
    collab.add_argument("--number", type=int)
    collab.add_argument("--title", default="")
    collab.add_argument("--json", action="store_true")
    collab.add_argument("--claim", action="store_true", help="Claim path/branch ownership (#651)")
    collab.add_argument("--release", nargs="?", const=True, default=None, help="Release claim by id (or --kind/--target)")
    collab.add_argument("--list-claims", action="store_true", help="List open ownership claims")
    collab.add_argument("--etiquette", action="store_true", help="Branch/worktree etiquette check")
    collab.add_argument("--concurrent", action="store_true", help="Concurrent-edit risk for --paths")
    collab.add_argument("--ownership-feed", action="store_true", help="Feed presentation for open claims")
    collab.add_argument("--kind", choices=["path", "branch"], default="path", help="Ownership kind for claim/release")
    collab.add_argument("--target", default="", help="Path or branch for claim/release")
    collab.add_argument("--owner", choices=["human", "agent", "collaborative"], default="human")
    collab.add_argument("--reason", default="", help="Claim reason")
    collab.add_argument("--status", default="open", help="Claim list status filter")
    collab.add_argument("--paths", default="", help="Comma-separated paths for policy/concurrent checks")
    collab.add_argument("--branch", default="", help="Branch name for policy/etiquette")
    collab.add_argument("--worktree-root", default="", help="Worktree path for isolation check")
    collab.add_argument("--repo-root", default="", help="Primary repo root for isolation check")
    collab.set_defaults(func=cmd_collab)

    task = sub.add_parser(
        "task",
        help="Create/close human Task issues (#359): required 6-field contract",
    )
    task.add_argument("--repo", help="owner/name")
    task.add_argument("--create", action="store_true", help="Create a Task issue")
    task.add_argument("--title", help="Task title (human action summary)")
    task.add_argument("--human-action", dest="human_action", default="", help="What the human must do")
    task.add_argument("--why", dest="why", default="", help="Why the agent cannot safely proceed")
    task.add_argument("--context", default="", help="Context and affected artifacts")
    task.add_argument("--instructions", default="", help="Best-effort next steps")
    task.add_argument("--done-signal", dest="done_signal", help="Override default done signal text")
    task.add_argument("--related", default="", help="Related links (text)")
    task.add_argument("--milestone", help="Milestone number or title")
    task.add_argument("--epic-milestone", dest="epic_milestone", help="Epic milestone title to inherit")
    task.add_argument("--close", type=int, metavar="N", help="Close Task #N with PLATE-TASK-CLOSED")
    task.add_argument("--comment", default="", help="Completion comment for --close")
    task.add_argument("--detect", action="store_true", help="Detect human-only blockers from --signal (#360)")
    task.add_argument("--signal", default="", help="Text signal to classify (CI log, error, note)")
    task.add_argument(
        "--apply",
        action="store_true",
        help="With --detect: create Task issues for blockers (default detect-only)",
    )
    task.add_argument("--dry-run", action="store_true")
    task.add_argument("--json", action="store_true")
    task.set_defaults(func=cmd_task)

    sops = sub.add_parser(
        "scheduled-ops",
        help="Scheduled autonomous ops catalog: refactor, release, deploy (#641)",
    )
    sops.add_argument("--list", action="store_true", help="List ops catalog")
    sops.add_argument("--status", action="store_true", help="Status + runnable at tolerance (default)")
    sops.add_argument("--plan", metavar="OP_ID", help="Emit agent packet for op")
    sops.add_argument("--run", metavar="OP_ID", help="Record op run (dry-run default)")
    sops.add_argument("--apply", action="store_true", help="Non-dry-run when risk allows")
    sops.add_argument("--approved", action="store_true", help="Human approved high/critical op")
    sops.add_argument("--checkpoint-id", dest="checkpoint_id", default="")
    sops.add_argument(
        "--shadow-ack",
        dest="shadow_ack",
        default="",
        help="shadow_id from prior dry-run/simulate for live high/critical ops (#645/#879)",
    )
    sops.add_argument("--risk-tolerance", dest="risk_tolerance", default="medium")
    sops.add_argument("--runs", action="store_true", help="List recorded runs")
    sops.add_argument("--op", default="", help="Filter runs by op id")
    sops.add_argument("--run-status", dest="run_status", default="all")
    sops.add_argument("--complete", metavar="RUN_ID")
    sops.add_argument("--complete-status", dest="complete_status", default="done")
    sops.add_argument("--note", default="")
    sops.add_argument("--limit", type=int, default=50)
    sops.add_argument(
        "--budget-remaining",
        dest="budget_remaining",
        type=int,
        default=None,
        help="Explicit remaining tokens for #634 gate (overrides live hydrate)",
    )
    sops.add_argument(
        "--no-live-budget",
        dest="no_live_budget",
        action="store_true",
        help="Do not hydrate budget from spend.json / .plate",
    )
    sops.add_argument("--json", action="store_true")
    sops.set_defaults(func=cmd_scheduled_ops)

    fmedia = sub.add_parser(
        "feature-media",
        help="Plan/register/approve per-Feature demo GIF/video (#636)",
    )
    fmedia.add_argument("--feature", type=int, help="Feature issue number")
    fmedia.add_argument("--title", default="", help="Feature title")
    fmedia.add_argument("--test-name", dest="test_name", default="", help="E2E test name for record_e2e_gif")
    fmedia.add_argument("--caption", default="")
    fmedia.add_argument("--fragment-slug", dest="fragment_slug", default="")
    fmedia.add_argument("--quality", default="medium")
    fmedia.add_argument("--list", action="store_true")
    fmedia.add_argument("--get", metavar="RECORD_ID")
    fmedia.add_argument("--register", metavar="RECORD_ID", help="Register capture result")
    fmedia.add_argument("--gif-path", dest="gif_path", default="")
    fmedia.add_argument("--size-bytes", dest="size_bytes", type=int)
    fmedia.add_argument("--decide", metavar="RECORD_ID")
    fmedia.add_argument("--decision", default="approve")
    fmedia.add_argument("--decided-by", dest="decided_by", default="human")
    fmedia.add_argument("--skip", metavar="RECORD_ID")
    fmedia.add_argument("--attach", metavar="RECORD_ID", help="Attach media to fragment JSON")
    fmedia.add_argument("--fragment", default="", help="Path to fragment JSON for --attach")
    fmedia.add_argument("--feed", action="store_true")
    fmedia.add_argument("--estimate-cost", dest="estimate_cost", action="store_true")
    fmedia.add_argument("--phase", default="plan", help="plan|register for --estimate-cost")
    fmedia.add_argument(
        "--budget-remaining",
        dest="budget_remaining",
        type=int,
        default=None,
        help="Override remaining tokens for #634 budget gate",
    )
    fmedia.add_argument(
        "--no-live-budget",
        dest="no_live_budget",
        action="store_true",
        help="Do not hydrate budget from spend.json / .plate",
    )
    fmedia.add_argument("--note", default="")
    fmedia.add_argument("--status", default="all")
    fmedia.add_argument("--limit", type=int, default=50)
    fmedia.add_argument("--json", action="store_true")
    fmedia.set_defaults(func=cmd_feature_media)

    hybrid = sub.add_parser(
        "hybrid",
        help="Hybrid/non-code project kinds, artifact types, validation plans (#650)",
    )
    hybrid.add_argument("--base-dir", dest="base_dir", default=".agentic/hybrid")
    hybrid.add_argument("--repo-root", dest="repo_root", default=".")
    hybrid.add_argument("--list", "--list-kinds", dest="list_kinds", action="store_true")
    hybrid.add_argument("--list-artifacts", dest="list_artifacts", action="store_true")
    hybrid.add_argument("--list-validation", dest="list_validation", action="store_true")
    hybrid.add_argument("--detect", action="store_true")
    hybrid.add_argument("--set-kind", dest="set_kind", metavar="KIND")
    hybrid.add_argument("--show", "--profile", dest="show", action="store_true")
    hybrid.add_argument("--template", metavar="KIND", help="Planning template for kind")
    hybrid.add_argument("--validation-plan", dest="validation_plan", action="store_true")
    hybrid.add_argument("--kind", default="")
    hybrid.add_argument("--title", default="")
    hybrid.add_argument("--contract", metavar="KIND")
    hybrid.add_argument("--feed", action="store_true")
    hybrid.add_argument("--note", default="")
    hybrid.add_argument("--json", action="store_true")
    hybrid.set_defaults(func=cmd_hybrid)

    packaging = sub.add_parser(
        "packaging",
        help="Marketplace packaging with media + adoption proof (#652); never auto-publishes",
    )
    packaging.add_argument("--releases-dir", dest="releases_dir", default=".agentic/releases")
    packaging.add_argument("--base-dir", dest="base_dir", default=".agentic/packaging")
    packaging.add_argument("--version", default="unreleased", help="Target version label for the package")
    packaging.add_argument("--list", action="store_true")
    packaging.add_argument("--get", metavar="PACKAGE_ID")
    packaging.add_argument("--render", metavar="PACKAGE_ID", nargs="?", const=True, help="Render package markdown (id or ephemeral with --version)")
    packaging.add_argument("--decide", metavar="PACKAGE_ID")
    packaging.add_argument("--decision", default="approve", help="approve|reject")
    packaging.add_argument("--decided-by", dest="decided_by", default="human")
    packaging.add_argument("--note", default="")
    packaging.add_argument("--feed", action="store_true")
    packaging.add_argument("--plan", action="store_true", help="Marketplace-package op packet")
    packaging.add_argument("--require-approved-media", dest="require_approved_media", action="store_true")
    packaging.add_argument("--no-persist", dest="no_persist", action="store_true")
    packaging.add_argument(
        "--budget-remaining",
        dest="budget_remaining",
        type=int,
        default=None,
        help="Explicit remaining tokens for #634 gate (overrides live hydrate)",
    )
    packaging.add_argument(
        "--no-live-budget",
        dest="no_live_budget",
        action="store_true",
        help="Do not hydrate budget from spend.json / .plate",
    )
    packaging.add_argument("--status", default="all")
    packaging.add_argument("--limit", type=int, default=20)
    packaging.add_argument("--json", action="store_true")
    packaging.set_defaults(func=cmd_packaging)

    rmedia = sub.add_parser(
        "release-media",
        help="Collect/render/approve GIF/video media for release notes (#635)",
    )
    rmedia.add_argument("--releases-dir", dest="releases_dir", default=".agentic/releases")
    rmedia.add_argument("--version", default="")
    rmedia.add_argument("--render", action="store_true", help="Print media markdown")
    rmedia.add_argument("--approved-only", dest="approved_only", action="store_true")
    rmedia.add_argument("--validate-paths", dest="validate_paths", action="store_true")
    rmedia.add_argument("--feed", action="store_true")
    rmedia.add_argument("--decide", action="store_true")
    rmedia.add_argument("--decision", default="approve")
    rmedia.add_argument("--index", type=int)
    rmedia.add_argument("--path", default="")
    rmedia.add_argument("--url", default="")
    rmedia.add_argument("--json", action="store_true")
    rmedia.set_defaults(func=cmd_release_media)

    dcontract = sub.add_parser(
        "design-contract",
        help="Design validation + visual/interaction contracts for Features (#646)",
    )
    dcontract.add_argument("--feature", type=int, help="Feature issue number")
    dcontract.add_argument("--title", default="", help="Feature title")
    dcontract.add_argument("--interactions", default="", help="Semicolon-separated interaction criteria")
    dcontract.add_argument("--visuals", default="", help="Semicolon-separated visual specs")
    dcontract.add_argument("--playwright", action="store_true", help="Include Playwright items in test plan")
    dcontract.add_argument("--draft", action="store_true", help="Keep as draft (no pending_approval)")
    dcontract.add_argument("--list", action="store_true")
    dcontract.add_argument("--get", metavar="CONTRACT_ID")
    dcontract.add_argument("--decide", metavar="CONTRACT_ID")
    dcontract.add_argument("--decision", default="approve")
    dcontract.add_argument("--decided-by", dest="decided_by", default="human")
    dcontract.add_argument("--validate", metavar="CONTRACT_ID")
    dcontract.add_argument("--scaffold", metavar="CONTRACT_ID", help="Print failing test scaffold")
    dcontract.add_argument("--lang", default="python", choices=["python", "typescript"])
    dcontract.add_argument("--feed", action="store_true")
    dcontract.add_argument("--note", default="")
    dcontract.add_argument("--status", default="all")
    dcontract.add_argument(
        "--budget-remaining",
        dest="budget_remaining",
        type=int,
        default=None,
        help="Explicit remaining tokens for #634 gate (overrides live hydrate)",
    )
    dcontract.add_argument(
        "--no-live-budget",
        dest="no_live_budget",
        action="store_true",
        help="Do not hydrate budget from spend.json / .plate",
    )
    dcontract.add_argument("--limit", type=int, default=50)
    dcontract.add_argument("--json", action="store_true")
    dcontract.set_defaults(func=cmd_design_contract)

    featloop = sub.add_parser(
        "feature-loop",
        help="Autonomous feature implementation loop orchestration (#639)",
    )
    featloop.add_argument("--repo", help="owner/name")
    featloop.add_argument("--feature", type=int, help="Feature issue number")
    featloop.add_argument("--title", default="", help="Feature title")
    featloop.add_argument("--risk", default="medium")
    featloop.add_argument("--risk-tolerance", dest="risk_tolerance", default="medium")
    featloop.add_argument("--size", default="medium", choices=["trivial", "small", "medium", "large"])
    featloop.add_argument("--labels", default="")
    featloop.add_argument("--pr", type=int)
    featloop.add_argument("--branch", default="")
    featloop.add_argument("--design", action="store_true", help="Include design validation cost")
    featloop.add_argument("--e2e", action="store_true")
    featloop.add_argument("--no-media", dest="no_media", action="store_true")
    featloop.add_argument("--budget-remaining", dest="budget_remaining", type=int)
    featloop.add_argument("--estimate", action="store_true", help="Cost estimate only")
    featloop.add_argument("--list", action="store_true")
    featloop.add_argument("--get", metavar="RUN_ID")
    featloop.add_argument("--advance", metavar="RUN_ID")
    featloop.add_argument("--tick", metavar="RUN_ID")
    featloop.add_argument("--cancel", metavar="RUN_ID")
    featloop.add_argument("--feed", action="store_true")
    featloop.add_argument("--apply", action="store_true")
    featloop.add_argument("--fetch-gates", dest="fetch_gates", action="store_true")
    featloop.add_argument("--skip-checkpoint", dest="skip_checkpoint", action="store_true")
    featloop.add_argument("--skip-media", dest="skip_media", action="store_true")
    featloop.add_argument("--note", default="")
    featloop.add_argument("--status", default="active")
    featloop.add_argument("--limit", type=int, default=50)
    featloop.add_argument("--json", action="store_true")
    featloop.set_defaults(func=cmd_feature_loop)

    bugloop = sub.add_parser(
        "bug-loop",
        help="Autonomous bug resolution loop orchestration (#638)",
    )
    bugloop.add_argument("--repo", help="owner/name")
    bugloop.add_argument("--bug", type=int, help="Bug issue number")
    bugloop.add_argument("--title", default="", help="Bug title")
    bugloop.add_argument("--risk", default="medium")
    bugloop.add_argument("--risk-tolerance", dest="risk_tolerance", default="medium")
    bugloop.add_argument(
        "--size",
        default="medium",
        choices=["trivial", "small", "medium", "large"],
        help="Size for cost estimate (#634/#638)",
    )
    bugloop.add_argument(
        "--budget-remaining",
        dest="budget_remaining",
        type=int,
        default=None,
        help="Explicit token remaining; omit to live-hydrate when autonomy on",
    )
    bugloop.add_argument(
        "--no-live-budget",
        dest="no_live_budget",
        action="store_true",
        help="Do not hydrate budget from spend.json",
    )
    bugloop.add_argument("--labels", default="", help="Comma labels for human-gate assessment")
    bugloop.add_argument("--pr", type=int, help="Existing PR number")
    bugloop.add_argument("--branch", default="")
    bugloop.add_argument("--list", action="store_true")
    bugloop.add_argument("--get", metavar="RUN_ID")
    bugloop.add_argument("--advance", metavar="RUN_ID")
    bugloop.add_argument("--tick", metavar="RUN_ID")
    bugloop.add_argument("--cancel", metavar="RUN_ID")
    bugloop.add_argument("--feed", action="store_true")
    bugloop.add_argument("--apply", action="store_true", help="With --tick: allow auto-advance when gates clean")
    bugloop.add_argument("--fetch-gates", dest="fetch_gates", action="store_true")
    bugloop.add_argument("--skip-checkpoint", dest="skip_checkpoint", action="store_true")
    bugloop.add_argument("--note", default="")
    bugloop.add_argument("--status", default="active")
    bugloop.add_argument("--limit", type=int, default=50)
    bugloop.add_argument("--json", action="store_true")
    bugloop.set_defaults(func=cmd_bug_loop)

    stub = sub.add_parser(
        "stub",
        help="Author/refine/create stub Issues of all types (#637)",
    )
    stub.add_argument("--repo", help="owner/name")
    stub.add_argument("--intent", default="", help="Free-text intent / Q&A answer")
    stub.add_argument("--title", default="", help="Optional explicit title")
    stub.add_argument("--type", dest="type", default="", help="Feature|Bug|Epic|Release|Research|Design|Question|Task")
    stub.add_argument("--summary", default="", help="Summary or refinement append")
    stub.add_argument("--source", default="qa")
    stub.add_argument("--parent-epic", dest="parent_epic", default=None)
    stub.add_argument("--list", action="store_true", help="List local drafts")
    stub.add_argument("--refine", metavar="DRAFT_ID", help="Refine draft by id")
    stub.add_argument("--add-acceptance", dest="add_acceptance", default="", help="Semicolon-separated AC lines")
    stub.add_argument("--note", default="")
    stub.add_argument("--ready", action="store_true", help="With --refine: mark ready-to-work")
    stub.add_argument("--create", metavar="DRAFT_ID", help="Create GitHub issue from draft")
    stub.add_argument("--apply", action="store_true", help="Actually create (default dry for --create; with --intent creates on GH)")
    stub.add_argument("--dry-create", dest="dry_create", action="store_true", help="After author, dry-run create payload")
    stub.add_argument("--feed", action="store_true")
    stub.add_argument("--status", default="all")
    stub.add_argument(
        "--budget-remaining",
        dest="budget_remaining",
        type=int,
        default=None,
        help="Explicit remaining tokens for #634 gate (overrides live hydrate)",
    )
    stub.add_argument(
        "--no-live-budget",
        dest="no_live_budget",
        action="store_true",
        help="Do not hydrate budget from spend.json / .plate",
    )
    stub.add_argument("--limit", type=int, default=50)
    stub.add_argument("--json", action="store_true")
    stub.set_defaults(func=cmd_stub)

    monitor = sub.add_parser(
        "monitor",
        help="Scheduled discussion review + market monitoring (#642)",
    )
    monitor.add_argument("--repo", help="owner/name for live discussion fetch")
    monitor.add_argument("--market", action="store_true", help="Run market signal synthesis")
    monitor.add_argument("--list-proposals", action="store_true", help="List monitor proposals")
    monitor.add_argument("--decide", metavar="PROPOSAL_ID", help="approve/reject a proposal")
    monitor.add_argument("--decision", default="approve", help="approve|reject|created")
    monitor.add_argument("--created-issue", dest="created_issue", type=int)
    monitor.add_argument("--feed", action="store_true", help="Feed items for pending proposals")
    monitor.add_argument("--apply", action="store_true", help="Persist proposals (default dry-run)")
    monitor.add_argument("--live", action="store_true", help="Fetch open Ideas discussions")
    monitor.add_argument("--title", default="", help="Market signal title (with --market)")
    monitor.add_argument("--detail", default="", help="Market signal detail")
    monitor.add_argument("--url", default="", help="Market signal URL")
    monitor.add_argument("--impact", default="medium", help="Signal impact low|medium|high")
    monitor.add_argument("--signals-json", dest="signals_json", default="", help="JSON array of signals")
    monitor.add_argument("--discussions-json", dest="discussions_json", default="", help="JSON array of discussions")
    monitor.add_argument("--source", default="", help="Filter proposals by source")
    monitor.add_argument("--status", default="pending", help="Proposal status filter")
    monitor.add_argument(
        "--budget-remaining",
        dest="budget_remaining",
        type=int,
        default=None,
        help="Explicit remaining tokens for #634 gate (overrides live hydrate)",
    )
    monitor.add_argument(
        "--no-live-budget",
        dest="no_live_budget",
        action="store_true",
        help="Do not hydrate budget from spend.json / .plate",
    )
    monitor.add_argument("--limit", type=int, default=50)
    monitor.add_argument("--json", action="store_true")
    monitor.set_defaults(func=cmd_monitor)

    fleet = sub.add_parser(
        "fleet",
        help="Multi-agent fleet handoffs + budget allocation (#644)",
    )
    fleet.add_argument("--roles", action="store_true", help="List fleet roles")
    fleet.add_argument("--handoff", action="store_true", help="Create agent→agent handoff")
    fleet.add_argument("--from-agent", dest="from_agent", default="orchestrator")
    fleet.add_argument("--to-agent", dest="to_agent", default="")
    fleet.add_argument("--task", default="", help="Handoff task description")
    fleet.add_argument("--complete", metavar="HANDOFF_ID", help="Mark handoff done")
    fleet.add_argument("--update", metavar="HANDOFF_ID", help="Update handoff status")
    fleet.add_argument(
        "--handoff-status",
        dest="handoff_status",
        default=None,
        help="Status for --update: open|accepted|done|blocked|cancelled",
    )
    fleet.add_argument(
        "--shadow-ack",
        dest="shadow_ack",
        default="",
        help="shadow_id for accepting high/critical handoffs (#645/#883)",
    )
    fleet.add_argument(
        "--approved",
        action="store_true",
        help="Human approved high/critical handoff accept (#645)",
    )
    fleet.add_argument(
        "--checkpoint-id",
        dest="checkpoint_id",
        default="",
        help="Approved #648 checkpoint id for high/critical accept",
    )
    fleet.add_argument("--list-handoffs", action="store_true", help="List handoffs")
    fleet.add_argument("--status", default="active", help="Filter: open|active|done|all")
    fleet.add_argument("--allocate", action="store_true", help="Split budget across roles")
    fleet.add_argument("--plan", metavar="INTENT", nargs="?", const="", help="Plan fleet from intent (dry-run unless --apply)")
    fleet.add_argument("--apply", action="store_true", help="With --plan: create handoffs")
    fleet.add_argument("--feed", action="store_true", help="Feed presentation for active handoffs")
    fleet.add_argument("--budget-tokens", dest="budget_tokens", type=int, default=None)
    fleet.add_argument(
        "--budget-remaining",
        dest="budget_remaining",
        type=int,
        default=None,
        help="Explicit remaining tokens for #634 gate (overrides live hydrate)",
    )
    fleet.add_argument(
        "--no-live-budget",
        dest="no_live_budget",
        action="store_true",
        help="Do not hydrate budget from spend.json / .plate",
    )
    fleet.add_argument("--risk", default="medium")
    fleet.add_argument("--active-roles", dest="active_roles", default="", help="Comma roles for --allocate")
    fleet.add_argument("--related-issue", dest="related_issue", type=int)
    fleet.add_argument("--related-pr", dest="related_pr", type=int)
    fleet.add_argument("--requires-human", dest="requires_human", action="store_true")
    fleet.add_argument("--note", default="")
    fleet.add_argument("--limit", type=int, default=50)
    fleet.add_argument("--json", action="store_true")
    fleet.set_defaults(func=cmd_fleet)

    pm = sub.add_parser(
        "pm",
        help="Project Manager orchestrator (#660): status, team personas, run assignment cycle",
    )
    pm.add_argument("--repo", help="owner/name")
    pm.add_argument("--status", action="store_true", help="Show PM status (default)")
    pm.add_argument("--team", action="store_true", help="List personas")
    pm.add_argument("--run", action="store_true", help="Run one orchestration cycle")
    pm.add_argument("--loop", action="store_true", help="Multi-cycle orchestrator loop")
    pm.add_argument("--queue", action="store_true", help="List durable assignment queue")
    pm.add_argument(
        "--queue-status",
        dest="queue_status",
        default="all",
        help="Filter queue: proposed|delegated|blocked|done|cancelled|all",
    )
    pm.add_argument(
        "--complete",
        metavar="ASSIGNMENT_ID",
        help="Mark assignment done/cancelled, or Approve & run with --complete-status run",
    )
    pm.add_argument(
        "--complete-status",
        dest="complete_status",
        default="done",
        help="Status for --complete: done|cancelled|run|approve (run = explicit delegate + dispatch)",
    )
    pm.add_argument("--note", default="", help="Note for --complete")
    pm.add_argument("--apply", action="store_true", help="With --run/--loop: attempt delegation (default dry-run)")
    pm.add_argument(
        "--no-tick-loops",
        dest="no_tick_loops",
        action="store_true",
        help="Skip syncing/completing delegated #638/#639 loops on --run",
    )
    pm.add_argument(
        "--fetch-loop-gates",
        dest="fetch_loop_gates",
        action="store_true",
        help="With --apply: fetch PR merge gates when ticking babysit loops",
    )
    pm.add_argument(
        "--tick-loops",
        dest="tick_loops",
        action="store_true",
        help="Tick delegated #638/#639 loops only (no new assigns); use --apply to advance estimate_cost/babysit",
    )
    pm.add_argument("--max-assignments", dest="max_assignments", type=int, default=5)
    pm.add_argument("--max-cycles", dest="max_cycles", type=int, default=3)
    pm.add_argument("--limit", type=int, default=50, help="Queue list limit")
    pm.add_argument("--json", action="store_true")
    pm.set_defaults(func=cmd_pm)

    autonomy = sub.add_parser("autonomy", help="Autonomy status, run cycle, and --loop for persistent budgeted long-running operation (Epic #470)")
    autonomy.add_argument("--repo", help="owner/name; defaults to git remote origin")
    autonomy.add_argument("--status", action="store_true", help="Show autonomy status (risk tolerance, budget, autopilot score)")
    autonomy.add_argument(
        "--budget",
        action="store_true",
        help="Show durable #634 budget snapshot (limits, spend, remaining, pressure; pairs with feature-loop hydrate)",
    )
    autonomy.add_argument(
        "--budget-reset",
        dest="budget_reset",
        action="store_true",
        help="Zero durable spend.json counters for the current UTC day (operator hygiene; does not change .plate limits)",
    )
    autonomy.add_argument(
        "--budget-reset-reason",
        dest="budget_reset_reason",
        default=None,
        help="Optional note stored on spend.json when using --budget-reset",
    )
    autonomy.add_argument(
        "--estimate-tokens",
        type=int,
        dest="estimate_tokens",
        default=None,
        help="With --budget: project would_pause/throttle for this token estimate",
    )
    autonomy.add_argument(
        "--simulate",
        metavar="ACTION",
        help="Shadow-simulate a high-impact action without side effects (#645); prints estimates + shadow_id",
    )
    autonomy.add_argument(
        "--scope",
        help="Optional JSON scope for --simulate (e.g. '{\"version\":\"1.0.0\"}')",
    )
    autonomy.add_argument("--run", action="store_true", help="Run one cycle (or with --loop)")
    autonomy.add_argument("--loop", action="store_true", help="Run multiple cycles (use --max-cycles)")
    autonomy.add_argument("--max-cycles", type=int, default=3, help="For --loop")
    try:
        autonomy.add_argument("--sleep-seconds", type=int, default=300, help="Sleep seconds between --loop cycles (defaults to .plate autonomy.loop.default_sleep_seconds or 300; use smaller for demo --loop)")
    except Exception:
        pass  # tolerate duplicate registration during parser build (post-rebase for #492)
    autonomy.add_argument("--dry-run", action="store_true", help="Dry run (no side effects)")
    autonomy.add_argument("--max-steps", type=int, help="Cap actions per cycle")
    try:
        autonomy.add_argument("--sleep-seconds", type=int, help="Sleep seconds between --loop cycles (overrides .plate autonomy.loop.default_sleep_seconds; default 300)")
    except Exception:
        pass  # tolerate duplicate registration during build_parser (CI fix for #493)
    autonomy.add_argument("--json", action="store_true", help="Output JSON")
    autonomy.set_defaults(func=cmd_autonomy)

    checkpoint = sub.add_parser(
        "checkpoint",
        help="Unified human checkpoint/approval primitive (#648): create, decide, list, get",
    )
    checkpoint.add_argument("--repo", help="owner/name; defaults to git remote origin")
    checkpoint.add_argument("--json", action="store_true", help="Output JSON")
    checkpoint.add_argument("--create", action="store_true", help="Create a checkpoint")
    checkpoint.add_argument("--title", help="Checkpoint title (with --create)")
    checkpoint.add_argument("--reason", help="Why judgment is required (with --create)")
    checkpoint.add_argument("--impact", default="medium", help="low|medium|high|critical")
    checkpoint.add_argument("--action-kind", dest="action_kind", default="", help="Gated action kind")
    checkpoint.add_argument("--shadow-id", dest="shadow_id", help="Optional #645 shadow_id")
    checkpoint.add_argument("--related-issue", dest="related_issue", type=int)
    checkpoint.add_argument("--related-pr", dest="related_pr", type=int)
    checkpoint.add_argument("--decide", metavar="ID", help="Decide on checkpoint id")
    checkpoint.add_argument(
        "--decision",
        choices=["approve", "revise", "reject", "cancel"],
        help="Decision for --decide",
    )
    checkpoint.add_argument("--note", default="", help="Decision note")
    checkpoint.add_argument("--by", dest="decided_by", default="cli-user", help="Actor for create/decide")
    checkpoint.add_argument("--list", action="store_true", help="List checkpoints (default pending)")
    checkpoint.add_argument("--open-only", dest="open_only", action="store_true", help="Only pausing open checkpoints")
    checkpoint.add_argument("--status", default="pending", help="Filter for --list (pending|all|approved|...)")
    checkpoint.add_argument("--get", metavar="ID", help="Get one checkpoint by id")
    checkpoint.set_defaults(func=cmd_checkpoint)

    rel_cut = release_sub.add_parser("cut", help="Cut a release: aggregate fragments to versioned dir (first-class MVP per #261)")
    rel_cut.add_argument("version", nargs="?", help="Explicit version e.g. vX.Y.Z (optional, auto-detect)")
    rel_cut.add_argument("--releases-dir", dest="releases_dir", help="Path to releases directory (default: .agentic/releases)")
    rel_cut.add_argument("--version-type", dest="version_type", choices=["major", "minor", "patch"], help="Override bump type for auto-detect")
    rel_cut.add_argument("--dry-run", action="store_true", help="Do not write files (dry-run)")
    rel_cut.add_argument("--json", action="store_true", help="Output JSON (future)")
    rel_cut.set_defaults(func=cmd_release_cut)

    # Finalize stub (plan step 8 for #313 / Epic #306): performs tag + triggers from .plate + spawn next Next Release.
    # MVP: prints guidance + invokes a couple core actions if configured; full in follow-ups.
    rel_finalize = release_sub.add_parser("finalize", help="Finalize a release: tag, kick .plate-configured downstream triggers, ensure next 'Next Release' issue (per refined ceremony)")
    rel_finalize.add_argument("version", nargs="?", help="The version being finalized (e.g. vX.Y.Z)")
    rel_finalize.add_argument("--releases-dir", dest="releases_dir", help="Path to releases directory (default: .agentic/releases)")
    rel_finalize.add_argument("--dry-run", action="store_true", help="Do not execute side effects (dry-run)")
    rel_finalize.add_argument(
        "--apply",
        action="store_true",
        help="Perform side effects including guarded hard-reset of the release branch. GitHub Release creation is attempted by default (idempotent via existence check).",
    )
    rel_finalize.add_argument("--json", action="store_true", help="Output JSON (future)")
    rel_finalize.set_defaults(func=cmd_release_finalize)

    rel_target = release_sub.add_parser(
        "target-epic",
        help="Validate an Epic against the active Next Release and print the manual issue-link step required by GitHub UI (#313)",
    )
    rel_target.add_argument("epic", help="Epic issue number to target to the current Next Release")
    rel_target.add_argument("--repo", help="owner/name")
    rel_target.add_argument("--json", action="store_true", help="Output JSON guidance")
    rel_target.set_defaults(func=cmd_release_target_epic)

    migrate = sub.add_parser("migrate", help="Migration plan/apply for template-to-plate cutover (Issue #131 / Epic #126)")
    migrate_sub = migrate.add_subparsers(dest="migrate_command", required=True)
    m_plan = migrate_sub.add_parser("plan", help="Dry-run migration plan")
    m_plan.add_argument("--repo", help="owner/name")
    m_plan.add_argument("--json", action="store_true")
    m_plan.set_defaults(func=cmd_migrate_plan)
    m_apply = migrate_sub.add_parser("apply", help="Apply migration (with checkpoints)")
    m_apply.add_argument("--repo", help="owner/name")
    m_apply.add_argument("--json", action="store_true")
    m_apply.set_defaults(func=cmd_migrate_apply)

    import_payload_p = sub.add_parser(
        "import-payload",
        help="Import PLATE template payload into a local checkout (dry-run/apply; #616)",
    )
    import_payload_p.add_argument(
        "--target-dir",
        default=".",
        help="Local target directory (default: cwd)",
    )
    import_payload_p.add_argument(
        "--strategy",
        choices=["safe", "conservative", "force"],
        default="safe",
        help="safe=skip existing; conservative=report conflicts; force=overwrite",
    )
    import_payload_p.add_argument(
        "--template-repo",
        help="Optional explicit template root path (default: package payload)",
    )
    import_payload_p.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Plan only (default). Use --apply to write files.",
    )
    import_payload_p.add_argument(
        "--apply",
        action="store_true",
        help="Write files according to strategy (disables dry-run).",
    )
    import_payload_p.add_argument(
        "--namespace-scripts",
        action="store_true",
        help="Force install PLATE scripts under scripts/plate/ (#621)",
    )
    import_payload_p.add_argument(
        "--no-namespace-scripts",
        action="store_true",
        help="Keep PLATE scripts at scripts/ even if target has scripts/",
    )
    import_payload_p.add_argument(
        "--escape-hatch",
        dest="escape_hatch",
        metavar="DIR",
        help="Write #622 plan.json + PLAN.md + DRAFT_PR_BODY.md under DIR (never auto-force)",
    )
    import_payload_p.add_argument(
        "--escape-hatch-on-conflict",
        action="store_true",
        help="If conflicts exist, write escape-hatch bundle under target/.agentic/import-escape-hatch (#622)",
    )
    import_payload_p.add_argument("--json", action="store_true", help="Output JSON report")
    import_payload_p.set_defaults(func=cmd_import_payload)

    spec_audit_p = sub.add_parser(
        "spec-audit",
        help="Audit SPEC.md vs release fragments and path citations (#338)",
    )
    spec_audit_p.add_argument(
        "--repo-root",
        default=".",
        help="Repository root containing SPEC.md (default: cwd)",
    )
    spec_audit_p.add_argument(
        "--spec",
        help="Optional path to SPEC.md",
    )
    spec_audit_p.add_argument(
        "--releases-dir",
        help="Optional path to .agentic/releases",
    )
    spec_audit_p.add_argument("--json", action="store_true", help="Output JSON report")
    spec_audit_p.add_argument(
        "--followups",
        action="store_true",
        help="Plan follow-up issues + SPEC draft from findings (#339)",
    )
    spec_audit_p.add_argument(
        "--apply-followups",
        action="store_true",
        help="Create follow-up GitHub issues (never writes SPEC.md; #339)",
    )
    spec_audit_p.add_argument(
        "--max-followups",
        type=int,
        default=10,
        help="Max actionable issues to plan/create (default 10)",
    )
    spec_audit_p.add_argument(
        "--show-draft",
        action="store_true",
        help="Print proposed additive SPEC markdown draft",
    )
    spec_audit_p.add_argument(
        "--repo",
        help="owner/name for issue creation (default: git remote)",
    )
    spec_audit_p.set_defaults(func=cmd_spec_audit)

    payload = sub.add_parser(
        "payload",
        help="Discover PLATE template payload (list/root/manifest/classify; #621)",
    )
    payload_sub = payload.add_subparsers(dest="payload_command")
    p_list = payload_sub.add_parser("list", help="List payload files + classification")
    p_list.add_argument("--template-repo", help="Optional explicit template root")
    p_list.add_argument("--include-excluded", action="store_true")
    p_list.add_argument("--json", action="store_true")
    p_list.set_defaults(func=cmd_payload, payload_command="list")
    p_root = payload_sub.add_parser("root", help="Resolve payload root path")
    p_root.add_argument("--template-repo", help="Optional explicit template root")
    p_root.add_argument("--json", action="store_true")
    p_root.set_defaults(func=cmd_payload, payload_command="root")
    p_man = payload_sub.add_parser("manifest", help="Show template payload manifest")
    p_man.add_argument("--json", action="store_true")
    p_man.set_defaults(func=cmd_payload, payload_command="manifest")
    p_cls = payload_sub.add_parser("classify", help="Classify a relative payload path")
    p_cls.add_argument("path", help="Relative path e.g. scripts/validate_plate_repo.sh")
    p_cls.add_argument("--template-repo", help="Optional explicit template root")
    p_cls.add_argument("--json", action="store_true")
    p_cls.set_defaults(func=cmd_payload, payload_command="classify")
    payload.set_defaults(func=cmd_payload, payload_command="list")

    qanda = sub.add_parser("qanda", help="Curiosity / Q&A Mode (list, view, record answers on Question issues; Epic #139)")
    qanda.add_argument("--repo", help="owner/name; defaults to git remote origin")
    qanda.add_argument("--json", action="store_true", help="Output JSON")
    qanda.add_argument("--list", action="store_true", help="List + synthesize priorities for open Questions (default)")
    qanda.add_argument("--synthesize", action="store_true", help="Just return prioritized list")
    qanda.add_argument("--question", type=int, help="Show full details for a specific Question number")
    qanda.add_argument("--record", type=int, help="Record an answer to this Question number")
    qanda.add_argument("--answer", help="Answer text when using --record")
    qanda.add_argument("--by", help="Who is answering (for provenance)", default="cli-user")
    qanda.add_argument("--limit", type=int, default=5, help="Max results for synthesize")
    qanda.set_defaults(func=cmd_qanda)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)
