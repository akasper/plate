# New PLATE Project Onboarding Questions — Design Spec

- **Issue:** #36
- **Designed by:** @copilot (agent session)
- **Date:** 2026-05-26
- **Status:** Draft

## Problem

A new PLATE project only works well when the system quickly learns the user's goals, constraints, and operating environment. Today the template has a `PLATE Configurator` agent and process artifacts, but it does not define a canonical set of onboarding questions or the order in which those questions should appear. Without that structure, teams get uneven setup quality, weak first-issue generation, and too much implicit context trapped in chat.

## Constraints

- The flow must work for a solo founder, a small engineering team, or an existing project adopting PLATE.
- The onboarding burden should stay light enough to finish in a first session.
- Questions should collect durable facts, not just temporary preferences.
- Answers must map to concrete repository artifacts, not vanish after the conversation.
- The sequence should support the whole journey: install PLATE tooling, create the repo, define the first epic, and land the first feature.
- Some answers should unlock recommended extensions, workflows, and future Question issues.

## Design Decision

Use a **staged onboarding conversation** driven by ordered information goals. Each stage asks only the minimum questions needed to safely unlock the next stage. Answers are persisted into repository artifacts and GitHub metadata so the project can continue asynchronously.

### Journey map

| Stage | User moment | PLATE output |
|---|---|---|
| 0 | `copilot plugin install akasper/plate_core` | PLATE capability becomes available locally |
| 1 | First repository setup | Repository bootstrap guidance, labels, base docs, recommended extensions |
| 2 | Team and operating-model setup | Project fields, notification defaults, risk posture, workflow expectations |
| 3 | Product definition | Initial `SPEC.md` direction, first epics, default Question backlog |
| 4 | Technical and operational context | CI scaffolding, stack choices, cost and compliance defaults |
| 5 | Cost, governance, and operational constraints | Cost posture, compliance defaults, artifact retention, and escalation routing |

### Persistence model

Each answer should land in one or more durable homes:

- `SPEC.md` for product intent, users, goals, constraints, and external integrations
- `CURRENT.md` only after behavior is implemented
- `.agentic/process.yml` or extension config for machine-readable defaults
- `.github/copilot-instructions.md` for stack-specific working guidance
- GitHub Projects fields for mutable operational state (priority, readiness, owner, cost class)
- New `Question` issues for follow-up information goals that cannot be answered in the first session

## Ordered Questions / Information Goals

### Stage 1 — Account and repository readiness

| # | Question / Goal | Why it matters | Feeds into project configuration |
|---|---|---|---|
| 1 | **Is Copilot cloud agent enabled for the account and available in this repository?** | PLATE's repo-level agents, issue automation, and future MCP integrations depend on cloud-agent availability. | Bootstrap checklist, repository readiness notes, follow-up `Question` if setup is incomplete. |
| 2 | **Is this a brand-new project or an existing codebase adopting PLATE?** | Migration projects need different extensions, docs, and risks than greenfield repos. | Extension recommendation (`migration`), bootstrap checklist, documentation scope. |
| 3 | **What is the repository name and one-sentence purpose?** | Gives the system a canonical project identity and prevents vague issue titles and specs. | `SPEC.md` Vision, README intro, issue templates, first epic wording. |
| 4 | **Who owns the repository and who can approve changes?** | Establishes the human judgment boundary early. | CODEOWNERS guidance, reviewer expectations, risk escalation notes. |

### Stage 2 — Team and operating model

| # | Question / Goal | Why it matters | Feeds into project configuration |
|---|---|---|---|
| 5 | **How many people will actively contribute (solo, 2-5, 6+)?** | Team size changes documentation needs, review burden, and whether wiki sync or custom agents are worthwhile. | Extension recommendations, GitHub Projects views, review cadence guidance. |
| 6 | **How do you prefer to work with PLATE: mostly autonomous, mostly human-gated, or mixed?** | Determines how aggressively agents should prepare PRs, batch questions, and recommend automation. | Agent guidance, autopilot recommendations, review expectations. |
| 7 | **What notification loop should PLATE optimize for?** (GitHub only, email, chat summary, daily digest) | Information goals are only useful if answers reach humans where they pay attention. | Documentation and follow-up workflow choices; future notification extension candidates. |
| 8 | **What is the acceptable review and risk posture?** (low-risk auto-prep only, human review on all merges, etc.) | Helps PLATE avoid over-automating sensitive repos. | Label defaults, review checklist emphasis, future autonomous-mode recommendations. |

### Stage 3 — Product and delivery context

| # | Question / Goal | Why it matters | Feeds into project configuration |
|---|---|---|---|
| 9 | **Who is the primary user and what problem are you solving for them?** | Anchors every future epic and prevents process-first planning detached from user value. | `SPEC.md` Users and Personas, Goals, initial epics. |
| 10 | **What does success look like in the first 30-60 days?** | Gives PLATE a near-term objective for issue decomposition and prioritization. | Initial roadmap, first Epic issue, acceptance criteria style. |
| 11 | **What is the first workflow or feature the team wants implemented?** | Converts abstract intent into an actionable first Epic and first Feature issue. | Epic label recommendation, feature backlog seed, wiki outline. |
| 12 | **Are there non-goals or scope boundaries we should protect?** | Autonomous systems need explicit guardrails, not just ambitions. | `SPEC.md` Non-Goals, issue-scoping guidance, follow-up Question issues. |

### Stage 4 — Technical stack and environment

| # | Question / Goal | Why it matters | Feeds into project configuration |
|---|---|---|---|
| 13 | **What tech stack do you prefer?** (language, framework, package manager, data store) | Determines testing, CI, bootstrapping, and agent instructions. | `.github/copilot-instructions.md`, CI placeholders, recommended labels/areas. |
| 14 | **What deployment environment do you target first?** (GitHub Pages, container platform, serverless, on-prem, mobile stores, etc.) | Changes extension recommendations and delivery workflow. | Deployment extension recommendations, `SPEC.md` Constraints, first infra issues. |
| 15 | **Which external systems or APIs are expected on day one?** | Prevents blocked implementation work and enforces PLATE's external-integration discipline. | `SPEC.md §External Integrations`, Research issues before implementation. |
| 16 | **What testing posture do you want by default?** (unit only, integration-heavy, Playwright E2E, manual evidence) | Determines the default verification path for feature work. | `tests/README.md`, `.github/copilot-instructions.md`, first CI customization steps. |

### Stage 5 — Cost, governance, and operational constraints

| # | Question / Goal | Why it matters | Feeds into project configuration |
|---|---|---|---|
| 17 | **How budget-sensitive is this project?** (prototype, moderate spend, strict cost cap) | Agent behavior, CI parallelism, and hosted-service recommendations should reflect budget reality. | `SPEC.md` Constraints, cost-focused Question issues, extension recommendations. |
| 18 | **Are there compliance, data residency, or security constraints?** | Some extensions and workflows are unsafe without this context. | `SPEC.md` Constraints, `need:security-review` guidance, extension allow/deny list. |
| 19 | **How should generated artifacts be retained?** (logs, screenshots, Playwright video, wiki evidence) | Affects testing cost, wiki sync, and documentation volume. | Testing guidance, wiki-sync strategy, retention notes in docs. |
| 20 | **Who should be interrupted when PLATE gets stuck or needs a decision?** | Ensures information goals escalate to the right human instead of stalling. | Review routing, CODEOWNERS guidance, future notification integrations. |

## Recommended first-session output

After answering the ordered questions above, PLATE should produce a concise setup bundle:

1. **Repository summary** — name, purpose, primary user, first success signal.
2. **Recommended extensions** — for example `migration`, `wiki-sync`, `custom-agents`.
3. **Initial Project fields** — e.g. `Priority`, `Risk`, `Cost Sensitivity`, `Needs Decision`.
4. **Three starter epics or fewer** — one should be the first implementation target.
5. **Default Question backlog** — only unanswered but important information goals.
6. **A first-feature brief** — enough detail to open a high-quality Feature issue immediately.

## Suggested artifact mapping

| Information gathered | Best durable home |
|---|---|
| Project purpose, users, goals, non-goals | `SPEC.md` |
| Team size, notification preference, risk posture | `.agentic/process.yml` or extension config + GitHub Project fields |
| Stack, testing, deployment defaults | `.github/copilot-instructions.md`, `tests/README.md`, CI scaffolds |
| External APIs and providers | `SPEC.md §External Integrations` |
| Unanswered onboarding gaps | `Question` issues |
| Enabled optional capabilities | `.agentic/extensions.yml` / future extension lock file |

## Alternatives Rejected

| Alternative | Why Rejected |
|---|---|
| Ask every possible setup question in one giant form | Too much upfront friction; users will either abandon the flow or provide low-quality answers. |
| Keep onboarding entirely conversational with no persistence target | Important context gets lost in chat and cannot drive future automation reliably. |
| Only use static forms with no adaptive follow-up | Misses migration edge cases, security concerns, and extension-specific branching. |
| Defer first-epic planning until after repository setup is complete | Leaves the user with a configured repo but no immediate productive next step. |

## Artifact

### Minimum default question set for all new PLATE projects

1. What is this project called, and what is its one-sentence purpose?
2. Is this greenfield or an existing project adopting PLATE?
3. Who are the primary users, and what outcome matters most to them?
4. How many active contributors will there be?
5. What tech stack and package ecosystem do you prefer?
6. Where will the project be deployed first?
7. Which testing posture should we assume by default?
8. How should PLATE notify or escalate to humans?
9. How budget-sensitive is this project?
10. What first Epic and first Feature should PLATE help define next?

### First feature handoff checklist

When onboarding is complete, PLATE should be able to generate a first Feature issue with:

- the target user and workflow
- acceptance criteria
- preferred test evidence
- documentation impact
- explicit risks or dependencies
- the matching `Epic: short-name` label recommendation

## Open Questions

1. Should PLATE store onboarding answers in a dedicated machine-readable file such as `.agentic/project-profile.yml`, or keep using distributed artifacts (`SPEC.md`, process config, issues)?
2. Should notification preferences remain documentation-only until a notification extension exists?
3. Should the onboarding flow create Question issues automatically, or stage them in a draft plan for human approval first?

## Acceptance Evidence

This design is correctly implemented when a new PLATE user can move from plugin install to a usable repository, first Epic, and first Feature issue without the agent having to rediscover basic project facts in later sessions.

Closes #36
