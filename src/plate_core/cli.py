"""CLI interface used by gh-plate extension entrypoint."""

from __future__ import annotations

import argparse
import json

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
from .epics import get_epic_status
from .features import detect_playwright_e2e_local, get_features
from .health import get_health
from .pr_babysit import babysit_pr


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


def cmd_bootstrap(args: argparse.Namespace) -> int:
    report = run_bootstrap(args.repo, apply_mode=args.apply)
    if args.json:
        print(json.dumps(report.to_dict()))
        return 0

    print(f"Repo: {report.repo}")
    print(f"Mode: {'APPLY' if report.apply_mode else 'DRY-RUN'}")
    for action in report.actions:
        print(f"- {action.name}: {action.state} ({action.detail})")
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
                    print(f"Sleeping {args.interval}s...\n")
                time.sleep(args.interval)
        except KeyboardInterrupt:
            return 0

    report = babysit_pr(
        pr_number=args.pr_number,
        repo=args.repo,
        agent_logins=args.agents,
        act=args.act,
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
    return 0


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
    )

    repo = getattr(args, "repo", None)
    json_out = getattr(args, "json", False)

    if getattr(args, "list", False) or args.command == "qanda" and not any(
        [getattr(args, "question", None), getattr(args, "synthesize", False), getattr(args, "record", False)]
    ):
        # Default: list + synthesize top priorities
        result = SynthesizePrioritiesTool.execute(repo=repo)
        if json_out:
            print(json.dumps(result))
            return 0
        print(f"Repo: {result.get('repo')}")
        print("Prioritized open Questions (Curiosity mode):")
        for i, q in enumerate(result.get("prioritized_questions", []), 1):
            print(f"  {i}. #{q.get('number')}: {q.get('title')}")
            print(f"     {q.get('html_url')}")
        print(f"\n{result.get('rationale', '')}")
        print("Tip: gh plate qanda --question N  |  --record N --answer 'text'")
        return 0

    if getattr(args, "synthesize", False):
        result = SynthesizePrioritiesTool.execute(repo=repo, max_results=getattr(args, "limit", 5))
        if json_out:
            print(json.dumps(result))
            return 0
        print(json.dumps(result, indent=2) if not json_out else "")
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

    if getattr(args, "record", None) and getattr(args, "answer", None):
        qnum = args.record
        result = RecordAnswerTool.execute(
            question_number=qnum,
            answer_text=args.answer,
            answered_by=getattr(args, "by", "cli-user"),
            repo=repo,
            source="manual",
        )
        if json_out:
            print(json.dumps(result))
            return 0
        print(f"Answer recorded for #{qnum}: {result.get('status')}")
        if result.get("comment_url"):
            print(f"Comment: {result['comment_url']}")
        print("Next: invoke Contemplation Engine to create follow-ups (see #149).")
        return 0

    # Fallback help
    print("gh plate qanda usage:")
    print("  gh plate qanda --list          # list + prioritize open Questions")
    print("  gh plate qanda --question 140  # details for one")
    print("  gh plate qanda --record 140 --answer 'The answer text here'")
    print("  gh plate qanda --synthesize --json")
    print("\nFor rich interactive sessions in Copilot CLI, the agent uses native TUI + these MCP tools.")
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
    skills = [skill.to_dict() for agent in list_skills()]:
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
    babysit.add_argument("--watch", action="store_true", help="Continuously monitor the PR")
    babysit.add_argument("--interval", type=int, default=60, help="Polling interval in seconds for --watch mode")
    babysit.add_argument("--json", action="store_true", help="Output JSON")
    babysit.set_defaults(func=cmd_pr_babysit)

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
