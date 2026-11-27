# PLATE concepts

This guide explains how PLATE organizes work on GitHub. It is written for humans adopting or operating a PLATE repository. Operating detail for agents lives in [AGENTS.md](../AGENTS.md); product intent lives in [SPEC.md](../SPEC.md).

PLATE (**Product Lifecycle Automation Toolkit and Engine**) treats GitHub as the default source of truth: issues for planning, milestones for epic grouping, labels for stable process metadata, workflows for gates, and pull requests for durable change. Shared tooling (`gh plate`, `plate-mcp`, and the CLI agent plugin) reads that state and drives health checks, release ceremony, autonomy, and PR-green loops. See [SPEC.md](../SPEC.md) §Purpose of PLATE and §Vision.

## How the pieces fit together

| Artifact | Role |
| --- | --- |
| [SPEC.md](../SPEC.md) | Human-owned product intent and goals (future state). |
| [AGENTS.md](../AGENTS.md) | Authority model, work loops, merge gates, and agent rules. |
| [`.plate`](../.plate) | Versioned JSON root config: methodology, extensions, autonomy, release hints. |
| [`.agentic/`](../.agentic/) | Repo-local machine artifacts: release fragments, procedures, costs, checkpoints, ledger. |
| GitHub Issues + Milestones | Planning, traceability, and epic containers. |
| GitHub Pull Requests | Implementation and documentation land here with type labels and `Closes #N`. |

Implemented behavior is recorded in [`.agentic/releases/`](../.agentic/releases/README.md) (per-feature **fragments** aggregated at release cut). The legacy [CURRENT.md](../CURRENT.md) file is deprecated in this repository; use fragments and release notes instead.

**Surfaces** (same library, different invocation):

| Surface | Typical use |
| --- | --- |
| `gh plate` | Terminal commands for humans and scripts. |
| `plate-mcp` | Structured MCP tools for coding agents. |
| CLI agent plugin | Conversational `/agent plate` with persona + MCP wiring. |

Install and first commands: [README.md](../README.md) §Quick Start and [starting-a-new-repository.md](bootstrap/starting-a-new-repository.md).

## Issue types

Every issue carries **exactly one** type label from the PLATE taxonomy (enforced by CI). Type labels define what “done” means and which artifact must exist when the issue closes. See [`.github/labels.yml`](../.github/labels.yml) and [AGENTS.md](../AGENTS.md) §Issue Artifact Rules.

| Type | Purpose | Typical closing artifact |
| --- | --- | --- |
| **Epic** | Parent planning object; children roll up to a GitHub **milestone** (canonical epic container). | Wiki summary or epic comment; epic-close PR when children are done. |
| **Feature** | New user-visible or operational capability. | Code PR + fragment under `.agentic/releases/unreleased/`. |
| **Bug** | Defect or regression. | Fix PR + regression test. |
| **Hardening** | Tests, CI reliability, isolation, or safety **without** new product capability. | PR + fragment with `change_type: "hardening"`. |
| **Task** | **Human-only** blocker or explicitly requested human action (credentials, marketplace publish, approvals agents cannot take). | Completion comment with `<!-- PLATE-TASK-CLOSED -->` (not necessarily a PR). |
| **Question** | Information goal; closes when the answer is committed. | Answer under `docs/research/` (and AGENTS/skills updates if guidance changes). |
| **Research** | Evidence gathering and options before product decisions. | `docs/research/<slug>.md` (or SPEC update if intent changes). |
| **Design** | UX, architecture, API, or data-model design. | `docs/design/<slug>.md` or wiki feature page. |
| **Release** | Planned release ceremony (standing **Next Release** or a versioned release issue). | Versioned `.agentic/releases/vX.Y.Z/` + tag + GitHub Release. |
| **Audit** | Drift or compliance finding. | `docs/audits/<slug>.md` + follow-up issues as needed. |
| **Migration** | Adoption or upgrade work on an existing repo. | `docs/migration/` updates. |
| **Documentation** | Documentation-only work tracked as an issue (same label family as documentation PRs). | Documentation PR. |

**Feedback Response** is a combined issue/PR type for work that addresses third-party agent review feedback when a dedicated issue is needed.

Agents and humans use the **Required Work Loop** in [AGENTS.md](../AGENTS.md) for each type (tests, fragments, base branch, labels, human review gates).

## Stubs and refinement

A **stub** is any issue that still lacks full scope or acceptance criteria. Stubs are normal: they preserve structure while details are discovered. Mark intentional stubs with `status:stub` and often `need:refinement`. See [stub-issues.md](agents/stub-issues.md).

During epic planning (`gh plate plan` / `plate_plan_epic`), children are often created as stubs (Research → Design → Feature) until refinement completes. Do not start implementation on a stub until refinement clears or required detail is present.

## Labels beyond type

Labels are **stable process metadata**, not a todo list. Frequent planning fields (priority, owner, target date) belong in GitHub Projects. From [AGENTS.md](../AGENTS.md) §Label Rules and [labels.yml](../.github/labels.yml):

| Family | Examples | Role |
| --- | --- | --- |
| **Release track** | `Major`, `Minor`, `Patch` | Declares which **next** integration branch this change targets during active development (`release-major`, `release-minor`, `release-patch`). |
| **area:*** | `area:docs`, `area:agent`, … | Subsystem or ownership. |
| **risk:*** | `risk:low` … `risk:critical` | Review burden and release caution; feeds autonomy and auto-merge policy. |
| **need:*** | `need:human-review`, `need:tests`, … | Missing input or required follow-up. |
| **status:*** | `status:stub`, `status:ready-to-work`, `status:blocked`, `status:implemented` | At most one `status:*` on an issue; `status:implemented` means merged to a release/**next** track but not yet shipped on `main`+tag (#556). |

Epic identity: use the GitHub **milestone** for the epic container; optional legacy `Epic: short-name` label may supplement.

## Release tracks and branches

PLATE uses a **multi-track release model**. During development, work labeled `Major` / `Minor` / `Patch` lands on the matching permissive **next** branch. Packaging creates a versioned branch and a Release PR to `main`. Full ceremony: [branch-model-and-ceremonies.md](agents/branch-model-and-ceremonies.md) and [release-ceremony-refinement.md](design/release-ceremony-refinement.md).

| Branch | Role |
| --- | --- |
| `epic/<short-name>` | Optional epic-owned branch; children merge via track branches. |
| `release-major`, `release-minor`, `release-patch` | Standing **next** integration lines tied to the open **Next Release** issue. |
| `release-vX.Y.Z` | Versioned stabilization branch for a concrete release. |
| `main` | Tagged stable history; only Release PRs merge here (merge commit, not squash). |

**Before opening a Feature, Bug, Hardening, or documentation PR**, run `gh plate release status` and set `--base` to the reported integration branch (for example `release-minor`), not `main`.

A single legacy `release` branch remains supported for repositories still on the older single-track model ([branch-model-and-ceremonies.md](agents/branch-model-and-ceremonies.md)).

Standing **Next Release** issue: one open issue titled **Next Release** (label `Release`) is the negotiation target for scope and linked epics. Packaging renames it to the concrete version (for example `v1.0.0`) and immediately spawns a fresh **Next Release**.

## Release fragments

**Fragments** are small JSON files under [`.agentic/releases/unreleased/`](../.agentic/releases/unreleased/README.md) (or per-epic directories) that describe a change for release notes and downstream migration. Feature and Hardening PRs that change process, templates, or product behavior **must** include a fragment; CI enforces this for Feature/Hardening PRs.

At release cut, `gh plate release cut` / `scripts/cut_release.py` collects fragments, infers semver (breaking → major, feature → minor, otherwise patch), and writes `.agentic/releases/vX.Y.Z/`. See [.agentic/releases/README.md](../.agentic/releases/README.md).

Pure documentation that does not change PLATE behavior or templates typically does **not** need a fragment ([documentation-rules.md](agents/documentation-rules.md)).

## Pull request lifecycle

1. **Branch** from the correct integration base (`gh plate release status`).
2. **Label** the PR with exactly one PR type: `Bug`, `Feature`, `Documentation`, `Hardening`, or `Feedback Response`.
3. **Link** the issue with `Closes #N`, `Fixes #N`, or `Resolves #N` in the PR body (warning gate if missing).
4. **Implement** with tests alongside code where the work loop requires them.
5. **Green CI** including **feedback-resolution** for unresolved third-party agent review threads.
6. **Human approval** for Bug, Feature, Hardening, and Documentation merges unless autonomous eligibility is fully met ([autonomous-mode.md](agents/autonomous-mode.md)).
7. **Merge** to the integration branch (squash for most work); Release PRs use merge commit to `main`.

Epic close: when all epic children are done, open a PR from `epic/<name>` → the appropriate release track, with a summary on the epic issue ([branch-model-and-ceremonies.md](agents/branch-model-and-ceremonies.md) §Epic-close ceremony).

Preflight: `gh plate pr preflight` / `gh plate pr verify` run read-only merge-readiness checks (labels, fragment, milestone, closing keyword, CI, review threads).

## Babysitting (PR green loop)

**Babysitting** is the local loop that keeps a PR mergeable: sync with base, fix CI, address review threads, and re-check gates. Prefer `gh plate pr babysit <number> [--act]` and MCP `plate_pr_babysit` / `plate_resolve_review_thread` over deprecated feedback workflows. Default branch update strategy is **local-rebase**; **copilot-request** is opt-in.

The agent (or human) diagnoses CI first (`gh pr checks`, failed job logs), fixes what is safe in an **isolated worktree**, pushes to the **same PR branch**, and resolves threads only after an in-thread reply. “Green” means feedback-resolution is clean and remaining blockers are human judgment (architecture, secrets, `need:human-review`). Details: [pr-feedback-and-babysit.md](agents/pr-feedback-and-babysit.md).

Configure which bot logins count as babysit targets via the `PLATE_PR_FEEDBACK_AGENTS` repository variable.

## Human Tasks

**Task** issues are explicitly **not** agent work. They exist when only a human can act: store credentials, approve marketplace publication, accept legal risk, or use an external account. The issue body should state the human action, why agents cannot proceed, and the done signal. Close with a short completion comment containing `<!-- PLATE-TASK-CLOSED -->`. See [AGENTS.md](../AGENTS.md) §Required Work Loop (Task).

Examples in this repo: marketplace publication Tasks referenced from [README.md](../README.md) §Marketplace release checklist.

## Questions and the feed

**Question** issues capture unknowns. Answers become durable artifacts (usually `docs/research/`). Batch review may use `/question-batch` or `scripts/question_batch.sh`. When an answer changes operating rules, update `AGENTS.md` and `.agentic/skills.yml` in the same PR.

The **feed** (`gh plate feed`, `plate_feed`) ranks open Questions and Tasks so humans and autonomy pick the next conversational or blocking item. Q&A planning flows can spawn approved stubs for Features, Epics, or Releases ([SPEC.md](../SPEC.md) §Target Workflows).

## Autonomy and `.plate`

**Autonomy** is engine-driven: `AutonomyEngine` reads health, budgets, procedures, and config, then decides safe next actions. Humans keep judgment on product intent, irreversible releases, and Tasks.

The **`autonomy`** section in [`.plate`](../.plate) is the single source of truth (replacing the legacy `.github/AUTONOMOUS_MODE` marker):

| Setting (conceptual) | Meaning |
| --- | --- |
| `risk_tolerance` | `off` \| `low` \| `medium` \| `high` — how much unattended progress is allowed (default philosophy is autonomy unless set to `off`; see [SPEC.md](../SPEC.md) §Goals). |
| `token_budget` / `cost_ceiling_usd` | Throttle or pause cycles when spend exceeds budget. |
| `schedules_enabled` / procedures | Recurring work under `.agentic/procedures/`. |
| `pr_review_scope` | Which review comments babysit considers (`all`, `bot-only`, `human-only`). |

Surfaces: `gh plate autonomy status|run|loop`, MCP `plate_autonomy_*`. Auto-merge of an agent’s own PRs is allowed only when autonomous mode is active **and** eligibility criteria in [autonomous-mode.md](agents/autonomous-mode.md) are satisfied (never for critical risk or protected paths like `AGENTS.md`, workflows, `SPEC.md`).

Broader `.plate` schema (methodology, extensions, overrides): [plate-root-config-schema-lifecycle.md](design/plate-root-config-schema-lifecycle.md).

## Authority: humans vs agents

| Area | Agents | Humans |
| --- | --- | --- |
| Product intent | Draft, clarify, map to issues | Final scope, priority, public commitments |
| Implementation | Code, tests, docs in approved tasks | Accept risk, merge approval, release approval |
| Process | Follow PLATE rules, suggest improvements | Change required gates or merge policy |
| Tasks | Document and escalate | Execute human-only actions |

Agents must not self-merge Bug/Feature/Hardening/Documentation PRs without meeting autonomous eligibility and human approval rules ([AGENTS.md](../AGENTS.md) §Merge and feedback gates).

## Where to go next

| Topic | Document |
| --- | --- |
| Bootstrap a new repo | [bootstrap/starting-a-new-repository.md](bootstrap/starting-a-new-repository.md) |
| Adopt PLATE on existing code | [migration/adoption-guide.md](migration/adoption-guide.md) |
| Release ceremony detail | [design/release-ceremony-refinement.md](design/release-ceremony-refinement.md) |
| Agent operating rules (full) | [AGENTS.md](../AGENTS.md) |
| Product intent | [SPEC.md](../SPEC.md) |
| MCP tools overview | [mcp.md](mcp.md) |
| Troubleshooting | [wiki/Troubleshooting.md](wiki/Troubleshooting.md) |
| 1.0 user-docs epic | GitHub issue [#1065](https://github.com/akasper/plate/issues/1065) (quickstart, reference, upgrade — sibling guides) |

---

*This guide was added for [#1067](https://github.com/akasper/plate/issues/1067). Terms are aligned to [SPEC.md](../SPEC.md) and repository labels as of the authoring PR.*