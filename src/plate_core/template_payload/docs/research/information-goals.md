# PLATE Information Goals Surface Area

- **Issue:** #40
- **Researched by:** @copilot (agent session)
- **Date:** 2026-05-26
- **Status:** Completed

## Research Question

How should PLATE proactively gather structured information from users through conversational interfaces? What is the best design space across forms, conversational agents, machine-readable configuration, persistence, and integration with PLATE's existing GitHub-native workflow system?

## Sources

- [Syntax for GitHub issue forms](https://docs.github.com/en/enterprise-cloud@latest/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-issue-forms)
- [About Projects](https://docs.github.com/en/issues/planning-and-tracking-with-projects/learning-about-projects/about-projects)
- [About single select fields](https://docs.github.com/en/issues/planning-and-tracking-with-projects/understanding-fields/about-single-select-fields)
- [Creating custom agents for Copilot cloud agent](https://docs.github.com/en/copilot/how-tos/use-copilot-agents/cloud-agent/create-custom-agents)
- [Custom agents configuration](https://docs.github.com/en/copilot/reference/custom-agents-configuration)
- [Connect Copilot cloud agent to external tools and data sources through MCP](https://docs.github.com/en/copilot/how-tos/use-copilot-agents/cloud-agent/extend-cloud-agent-with-mcp)
- [Model Context Protocol introduction](https://modelcontextprotocol.io/introduction)
- Existing PLATE artifacts: `AGENTS.md`, `.agentic/process.yml`, `.agentic/skills.yml`, `.github/agents/plate-configurator.agent.md`, `.github/ISSUE_TEMPLATE/question.yml`

## Findings

### 1. PLATE already has the right conceptual primitive: `Question` issues

PLATE already defines `Question` issues as **information goals** that close with committed answer artifacts. That is a strong foundation because it gives the system:

- a durable backlog item
- a human-reviewable prompt for missing information
- a traceable closing artifact
- an easy fit with GitHub automation and CI

The main gap is not the issue type itself. The gap is the **surface area for collecting answers** and **where stable answers should live** after they are known.

### 2. Forms and conversations solve different parts of the problem

| Approach | Strengths | Weaknesses | Best use in PLATE |
|---|---|---|---|
| **Issue forms / static forms** | Deterministic, structured, easy to validate, GitHub-native | Rigid, poor at follow-up, asks irrelevant questions | Initial capture of required facts |
| **Conversational custom agent** | Adaptive, can explain tradeoffs, can branch based on answers | Harder to guarantee structure unless answers are persisted explicitly | Discovery, clarification, and prioritization |
| **YAML / config file** | Machine-readable, versionable, easy for automation | Hard for new users to author from scratch | Canonical storage for durable defaults |
| **Pure chat with no persistence** | Lowest friction in the moment | Loses context, hard to audit, cannot reliably drive workflows | Should not be a primary PLATE mechanism |

The evidence strongly supports a **hybrid model**, not a winner-take-all model.

### 3. Recommended persistence split

The gathered information does not all belong in one place.

| Information type | Best persistence target |
|---|---|
| Product intent, users, goals, constraints | `SPEC.md` |
| Implemented behaviors and proof | `CURRENT.md` |
| Stable operational defaults (team size, stack, budget posture, notification preference) | Future machine-readable project profile such as `.agentic/project-profile.yml` |
| Open unknowns | `Question` issues |
| Mutable planning state (priority, readiness, cost class, owner) | GitHub Projects fields |

This matters because GitHub Projects are excellent for mutable metadata, but poor for rich narrative product intent. Conversely, `SPEC.md` is ideal for narrative truth, but not for every machine-consumable default.

### 4. Best interaction model: staged conversation backed by structure

PLATE should not ask every question in a single form or a single long chat. The best model is:

1. **Seed required facts** from a short structured intake.
2. **Use a custom agent** to ask adaptive follow-ups and explain tradeoffs.
3. **Persist answers immediately** into durable artifacts.
4. **Convert unanswered but important gaps** into tracked `Question` issues.

This is especially important because GitHub custom agents can be repository-scoped and tailored to onboarding workflows, while MCP can later add deterministic access to external tools if PLATE needs deeper orchestration.

### 5. YAML vs dynamic questioning is not an either/or

A useful framing is:

- **YAML stores decisions**
- **conversation discovers decisions**

Trying to replace conversation with YAML makes onboarding feel like paperwork. Trying to replace durable configuration with chat makes automation fragile. The strongest PLATE design is to let the agent gather answers conversationally, then commit the resulting defaults into machine-readable form.

### 6. MCP is promising, but not the first requirement

MCP provides a standard way for agents to use external tools and systems. That makes it a strong future fit for advanced PLATE experiences such as:

- reading deployment state from cloud providers
- checking monitoring systems
- inspecting project-management or incident tools
- pulling organization policy context

However, MCP does **not** solve the core onboarding problem by itself. It expands what the agent can inspect or act on; it does not replace the need for a durable information model. For PLATE's current stage, custom agents + GitHub-native artifacts are the higher-priority default.

## Recommendation

### Primary recommendation: adopt a hybrid information-goals architecture

PLATE should use four layers together:

| Layer | Role | Default? |
|---|---|---|
| **Required intake questions** | Capture universal baseline facts for every new project | Yes |
| **Conversational onboarding agent** | Ask adaptive follow-up questions and recommend extensions / workflows | Yes |
| **Durable project profile** | Store stable answers in machine-readable form | Yes, once a profile file schema is defined |
| **Question issue backlog** | Track unresolved or newly discovered information goals | Yes |

### Proposed default behavior for a new PLATE repo

1. User creates or bootstraps a repo.
2. PLATE asks a **small default question set** (purpose, team size, stack, deployment target, notification preference, budget sensitivity).
3. The configurator agent asks adaptive follow-ups only where needed.
4. Stable answers are written into:
   - `SPEC.md`
   - `.github/copilot-instructions.md`
   - a future `.agentic/project-profile.yml`
5. Remaining unknowns become `Question` issues.
6. GitHub Projects fields track mutable state such as priority, readiness, cost class, and decision-needed status.

### Why this is the best fit for PLATE

- It preserves PLATE's GitHub-native evidence model.
- It avoids betting everything on a non-extensible `/plate` command surface.
- It gives agents structured inputs without forcing users into an all-form experience.
- It creates a path to future MCP-based capabilities without blocking on them now.
- It aligns with the existing `Question` issue type instead of inventing a separate concept.

## Option assessment

| Option | Recommendation |
|---|---|
| Forms only | Too rigid as the primary experience |
| Conversation only | Too lossy and hard to automate |
| YAML only | Too heavy for first-time users |
| MCP-first | Promising later, but premature as the default |
| **Hybrid: form + conversation + durable profile + question backlog** | **Recommended** |

## Implementation implications for PLATE

The research suggests a practical sequence of follow-up work:

1. Define the **default question set** for every new project.
2. Extend the **PLATE Configurator** agent to ask those questions in a staged order.
3. Define a **project profile schema** for stable machine-readable answers.
4. Keep using `Question` issues for unresolved information goals.
5. Add optional `gh` extension or MCP tooling later for deterministic reporting and deeper integrations.

## Recommendation Summary

| Design question | Recommendation |
|---|---|
| Form-based or conversational? | Use both, with conversation layered on top of a short structured intake |
| YAML or dynamic questioning? | Use dynamic questioning to discover answers, YAML to persist them |
| Where should answers live? | Split across `SPEC.md`, a future project profile file, Projects fields, and Question issues |
| How should it integrate with PLATE workflows? | Feed issue creation, configurator guidance, CI docs, and extension recommendations |
| Should MCP be the default surface? | No, not yet |

Closes #40
