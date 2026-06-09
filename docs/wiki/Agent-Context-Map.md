# Agent Context Map

Use this page or `gh plate context list/show` when the question is **where should I look first?**

The canonical machine-readable equivalents are `gh plate context list/show` and the MCP tools `plate_contexts` / `plate_context`.

| Concern | First step | Authoritative artifacts | Machine surfaces | References |
|---|---|---|---|---|
| `process` — process / ceremony / PR rules | Open `AGENTS.md`. | `AGENTS.md` | `gh plate context show process` | `docs/design/cost-control-layered-agent-context-architecture.md` |
| `product-intent` — intended product or process goal state | Open `SPEC.md`. | `SPEC.md` | `gh plate context show product-intent` | `docs/design/cost-control-layered-agent-context-architecture.md` |
| `implemented-behavior` — implemented behavior / release evidence | Inspect `.agentic/releases/` or diff with `gh plate release notes`. | `.agentic/releases/` | `gh plate release notes`<br>`plate_release_notes` | `docs/wiki/Agent-Context-Map.md` |
| `agent-skill-discovery` — agent / skill lookup | Run `gh plate agents list` or `gh plate skills list`. | `src/plate_core/data/baseline_catalog.yml` | `gh plate agents list/show`<br>`gh plate skills list/show`<br>`plate_agents`<br>`plate_agent`<br>`plate_skills`<br>`plate_skill` | `docs/design/agent-skill-registry-and-discovery.md` |
| `release-targeting` — release targeting and integration branch choice | Run `gh plate release status`. | `live GitHub release state`<br>`AGENTS.md §Branch Model and Ceremonies` | `gh plate release status`<br>`plate_release_status` | `docs/design/release-ceremony-refinement.md` |
| `bootstrap-onboarding` — bootstrap / onboarding / initial PLATE setup | Open `docs/bootstrap/new-repository-checklist.md`. | `docs/bootstrap/new-repository-checklist.md`<br>`bootstrap scripts` | `gh plate bootstrap --apply`<br>`plate_bootstrap` | `docs/bootstrap/new-repository-checklist.md` |
| `delegation` — delegation and narrow task handoff | Call `plate_delegate_to_agent` or `gh plate agents delegate`. | `catalog metadata`<br>`docs/design/cost-control-narrow-delegation-packets.md` | `gh plate agents delegate`<br>`plate_delegate_to_agent` | `docs/design/cost-control-narrow-delegation-packets.md`<br>`docs/design/single-agent-delegation-flow.md` |

## Routing rules

1. Start here when the task is discovery, not execution.
2. Use live-state commands before prose when the answer depends on current GitHub or repository state.
3. Use authority artifacts before deep design/research docs when the answer is normative.
4. Open reference docs only for rationale, background, or implementation tradeoffs.
