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
from .pr_babysit import babysit_pr
from .release import (
    cleanup_dead_branches,
    cut_release as core_cut_release,
    get_release_notes_diff,
    get_release_status,
    get_release_target_epic_guidance,
)
from .migration import generate_migration_plan, apply_migration_plan
from .costs import get_cost_report
from .autonomy import AutonomyEngine, get_autonomy_status, run_autonomy_cycle
from .plate_config import (
    PlateConfigError,
    apply_plate_config_upgrade,
    get_plate_config_report,
    init_plate_config,
)


def cmd_health(args: argparse.Namespace) -> int:
    report = get_health(args.repo)
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
    return 0 if report.status != "fail" else 1


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
    try:
        report = run_bootstrap(args.repo, apply_mode=args.apply)
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
    print(f"Template source: {report.template_source}")
    for action in report.actions:
        print(f"- {action.name}: {action.state} ({action.detail})")
    return 0


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
                )
                if args.json:
                    print(json.dumps(report.to_dict()))
                else:
                    print(f"Repo: {report.repo} | PR #{report.pr_number}")
                    print(
                        f"Detected threads: {report.detected_threads}, actionable: {report.actionable_threads}, "
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
    )
    if args.json:
        print(json.dumps(report.to_dict()))
        return 0

    print(f"Repo: {report.repo}")
    print(f"PR: #{report.pr_number}")
    print(f"Detected threads: {report.detected_threads}")
    print(f"Actionable third-party threads: {report.actionable_threads}")
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
    from .costs import format_cost_markdown, get_cost_report

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
        if status.get("budget_remaining_tokens") is not None:
            print(f"Budget remaining tokens: {status.get('budget_remaining_tokens')}")
        print(f"Last cycle: {status.get('last_cycle')}")
        return 0

    # Default to status (safe) unless explicit --run or --loop provided. --run flag is now honored as explicit run.
    run = getattr(args, "run", False)
    loop = getattr(args, "loop", False)
    if not run and not loop:
        status = get_autonomy_status(args.repo)
        if getattr(args, "json", False):
            print(json.dumps(status))
            return 0
        print(f"Enabled: {status.get('enabled')}")
        print(f"Risk tolerance: {status.get('risk_tolerance')}")
        print("(no --run/--loop; showed status only. Use --run or --loop to execute a cycle.)")
        return 0

    dry_run = getattr(args, "dry_run", False)
    max_steps = getattr(args, "max_steps", None)
    # Use --sleep-seconds if provided (addresses copilot review on hard-coded 2s); else .plate config default or 300 (per docs and prior fixes, not 2s).
    sleep_s = getattr(args, "sleep_seconds", None)
    if sleep_s is None:
        sleep_s = 300
        try:
            eng = AutonomyEngine(repo=args.repo)
            sleep_s = eng.autonomy_config.get("loop", {}).get("default_sleep_seconds", 300) or 300
        except Exception:
            pass
    if loop:
        import time
        max_cycles = getattr(args, "max_cycles", 3) or 3
        for i in range(int(max_cycles)):
            if not getattr(args, "json", False):
                print(f"Cycle {i+1}/{max_cycles} (dry_run={dry_run})...")
            rep = engine.run_cycle(dry_run=dry_run, max_steps=max_steps)
            if hasattr(rep, "to_dict"):
                rep = rep.to_dict()
            if args.json:
                print(json.dumps(rep))
            else:
                print(f"  status={rep.get('status')} budget={rep.get('budget_decision')} actions={len(rep.get('actions_taken', []))}")
            if i < int(max_cycles) - 1:
                time.sleep(sleep_s)
        return 0

    rep = run_autonomy_cycle(repo=args.repo, dry_run=dry_run, max_steps=max_steps)
    if getattr(args, "json", False):
        print(json.dumps(rep))
        return 0
    print(f"Autonomy cycle: {rep.get('status')}")
    print(f"Budget decision: {rep.get('budget_decision')}")
    print(f"Actions taken: {rep.get('actions_taken', [])}")
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
    """Finalize stub for refined ceremony (Epic #306 / #313).
    In the current automation model, GitHub Actions owns the initial tag creation on merged
    Release PRs. finalize remains the surface for downstream triggers, rollover/repair, and
    any post-tag follow-up automation.
    """
    version = getattr(args, "version", None) or "vX.Y.Z"
    dry_run = getattr(args, "dry_run", False)
    print(f"Running release finalize for {version} (dry_run={dry_run})...")
    print("Steps (MVP stub; full impl follows design):")
    print("  1. Verify the merged Release PR created/pushed the expected git tag")
    print("  2. Load .plate['release']['triggers'] (or defaults)")
    print("  3. Invoke core triggers (e.g. render_release_notes)")
    print("  4. Create/ensure next 'Next Release' issue (label Release)")
    print("  5. Update status, post to Epic if linked")
    if dry_run:
        print("[DRY RUN] No side effects executed.")
        return 0
    # TODO: wire to core_finalize when implemented in release.py
    print("Finalize guidance complete. (Hook for actual tag/triggers in next slice.)")
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
    health.add_argument("--json", action="store_true", help="Output JSON")
    health.set_defaults(func=cmd_health)

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
    bootstrap.add_argument("--json", action="store_true", help="Output JSON")
    bootstrap.set_defaults(func=cmd_bootstrap)
    # Note: Goals page init (per #266) is included automatically when wiki enabled and page absent (plan in dry-run, apply with --apply). Flag/interactive refinement in future.

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
        help="Monitor a PR for actionable third-party feedback and optionally post a local babysit trigger",
    )
    babysit.add_argument("pr_number", type=int, help="Pull request number")
    babysit.add_argument("--repo", help="owner/name; defaults to git remote origin")
    babysit.add_argument(
        "--agents",
        help="Comma-separated GitHub logins to treat as third-party agents. Defaults to known patterns.",
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

    release = sub.add_parser("release", help="Release status and notes diff (read-only MVP)")
    release_sub = release.add_subparsers(dest="release_command", required=True)
    rel_status = release_sub.add_parser("status", help="Show current release status")
    rel_status.add_argument("--repo", help="owner/name; defaults to git remote origin")
    rel_status.add_argument("--releases-dir", dest="releases_dir", help="Path to releases directory (default: .agentic/releases)")
    rel_status.add_argument("--json", action="store_true", help="Output JSON")
    rel_status.set_defaults(func=cmd_release_status)
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
    costs.add_argument("--json", action="store_true", help="Output JSON")
    costs.set_defaults(func=cmd_costs)

    autonomy = sub.add_parser("autonomy", help="Autonomy status, run cycle, and --loop for persistent budgeted long-running operation (Epic #470)")
    autonomy.add_argument("--repo", help="owner/name; defaults to git remote origin")
    autonomy.add_argument("--status", action="store_true", help="Show autonomy status (risk tolerance, budget, autopilot score)")
    autonomy.add_argument("--run", action="store_true", help="Run one cycle (or with --loop)")
    autonomy.add_argument("--loop", action="store_true", help="Run multiple cycles (use --max-cycles)")
    autonomy.add_argument("--max-cycles", type=int, default=3, help="For --loop")
    autonomy.add_argument("--sleep-seconds", type=int, help="Sleep between loop cycles (defaults to .plate autonomy.loop.default_sleep_seconds or 2)")
    autonomy.add_argument("--dry-run", action="store_true", help="Dry run (no side effects)")
    autonomy.add_argument("--max-steps", type=int, help="Cap actions per cycle")
    autonomy.add_argument("--json", action="store_true", help="Output JSON")
    autonomy.add_argument("--sleep-seconds", type=int, help="Sleep between --loop cycles (defaults to .plate autonomy.loop.default_sleep_seconds or 2)")
    autonomy.set_defaults(func=cmd_autonomy)

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
