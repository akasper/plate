# v1.0 autonomy surface epics — closeout status

**As of 2026-07-26 on `release`:** First-class runtime surfaces for the #654 path are **landed** as implementable modules + fragments. This page is durable epic memory so agents do not re-sketch closed first slices.

| Epic | Title | Status | What shipped (summary) | Residual / non-goals |
|---|---|---|---|---|
| **#456** | Quiet Agents | **Close** | `QUIET_OPERATIONS_GUIDANCE`, persona quiet rules, audit/closeout migration note | Host auto-quiet UI N/A |
| **#637** | Stub authoring / refine lifecycle | **Close (first slice)** | Stub budget gates, planning/stub surfaces under unreleased `634-637-*` / stubs module | Full E2E “author every type from Q&A only” still #654 proof |
| **#638** | Full autonomous bug loop | **Close (first slice)** | `bug_loop.py`, PM/fleet dispatch, ticks, checkpoints, babysit stages | Production E2E bug→merge proof under #654 |
| **#639** | Full autonomous feature loop | **Close (first slice)** | `feature_loop.py`, media/design gates, PM dispatch, ticks | Production E2E feature→merge proof under #654 |
| **#641** | Scheduled autonomous ops | **Close (first slice)** | `scheduled_ops.py` catalog, fleet dispatch, monitor ops #642, shadow/budget gates | Real deploy/publish remain human Tasks |
| **#644** | Multi-agent fleet handoffs | **Close (first slice)** | `fleet.py` handoffs, accept→loop/artifact dispatch, feed items, PM bridge | Remote multi-agent host runtime N/A |
| **#660** | Project Manager orchestrator | **Open** | `pm.py` assign/loop/queue/MCP; artifact dispatch; what_next PM rank | Child **#661** browser deferred; keep epic open until browser decision or explicit deferral comment |

## Operator path (current)

```bash
gh plate what-next
gh plate pm --status
gh plate autonomy --status
gh plate scheduled-ops --status
gh plate fleet --roles
gh plate feed
```

## Human-only still blocking v1 packaging claims

- Marketplace/PyPI publish Tasks: **#380**, **#381**, **#625**, **#626**
- Do not check #654 boxes without E2E proof (sketches ≠ done)

## Links

- Release #654 roadmap; Autonomy Engine #470; feed/planning #656; design `docs/design/pm-orchestrator-architecture-and-browser.md`
- Fragments under `.agentic/releases/unreleased/` for each surface slug
