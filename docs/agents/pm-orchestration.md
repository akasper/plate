# Pm Orchestration

Part of the PLATE agent operating rules (formerly in `AGENTS.md`). The always-loaded core is [AGENTS.md](../AGENTS.md).

## Project Manager / Orchestration Guidance (#660 / #662)

When PLATE signals are present, long-running coordination prefers the **Project Manager** stack above raw AutonomyEngine loops:

1. `plate_what_next` / `gh plate what-next` for the next process step (open PRs → budget gates → PM → ready issues).
2. `plate_pm_status` / `plate_pm_run_cycle` (dry-run first when risk unknown) to assign work to persona team agents within budget and open checkpoints.
3. Delegated implement/bug work opens feature/bug loops; design/research opens #632 artifact proposals; fleet handoffs (#644) accept into the same surfaces.
4. Humans keep judgment at checkpoints, high-risk paths, and external Tasks. Drivers: prefer `driver:human` / `driver:agent` / `driver:collaborative` labels when present; do not force-push human-driven work.
5. Browser dashboard (#661) is out of scope for default agents — TUI `ask_user_question` + feed is the current surface.

Design detail: `docs/design/pm-orchestrator-architecture-and-browser.md`. Quiet ops and USAGE REPORT rules still apply.
