# v1.0 autonomy surface epics — closeout status

**As of 2026-07-26 on `release`:** First-class runtime surfaces for the #654 path are **landed** as implementable modules + fragments. This page is durable epic memory so agents do not re-sketch closed first slices.

| Epic | Title | Status | What shipped (summary) | Residual / non-goals |
|---|---|---|---|---|
| **#456** | Quiet Agents | **Close** | `QUIET_OPERATIONS_GUIDANCE`, persona quiet rules, audit/closeout migration note | Host auto-quiet UI N/A |
| **#470** | Autonomous PLATE Engine & Scheduled Procedures | **Close (first slice)** | AutonomyEngine, `.plate` autonomy schema, procedures, CLI/MCP `plate_autonomy_*`, budget/observability, SPEC align #488; children #471–#482 + #488 **13/13** | Unsupervised production loops still need risk≠off + E2E under #654 |
| **#637** | Stub authoring / refine lifecycle | **Close (first slice)** | Stub budget gates, planning/stub surfaces under unreleased `634-637-*` / stubs module | Full E2E “author every type from Q&A only” still #654 proof |
| **#638** | Full autonomous bug loop | **Close (first slice)** | `bug_loop.py`, PM/fleet dispatch, ticks, checkpoints, babysit stages | Production E2E bug→merge proof under #654 |
| **#639** | Full autonomous feature loop | **Close (first slice)** | `feature_loop.py`, media/design gates, PM dispatch, ticks | Production E2E feature→merge proof under #654 |
| **#641** | Scheduled autonomous ops | **Close (first slice)** | `scheduled_ops.py` catalog, fleet dispatch, monitor ops #642, shadow/budget gates | Real deploy/publish remain human Tasks |
| **#644** | Multi-agent fleet handoffs | **Close (first slice)** | `fleet.py` handoffs, accept→loop/artifact dispatch, feed items, PM bridge | Remote multi-agent host runtime N/A |
| **#656** | Q&A planning + endless feed | **Close (first slice)** | Product/feature/release Q&A planning (#628–#630/#640), Q+Task feed (#631), Design/Research approval (#632); children **6/6** | Host TUI polish + full E2E planning→ship under #654 |
| **#657** | Autonomy foundations (sim/checkpoint/budget/ledger) | **Close (first slice)** | Shadow/sim #645, checkpoint primitive #648, budgets #634, cost/risk feed #653, ledger #647; children **5/5** | Production high-impact gate E2E under #654 |
| **#658** | Evidence, media, packaging outcomes | **Close (first slice)** | Release-note media #635, feature media #636, packaging media #652; children **3/3** | Marketplace human publish Tasks remain out of band |
| **#660** | Project Manager orchestrator | **Open** | `pm.py` assign/loop/queue/MCP; artifact dispatch; what_next PM rank; active-only queue (#903/#904) | Child **#661** browser deferred; keep epic open until browser decision or explicit deferral comment |

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
