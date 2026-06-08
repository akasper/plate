# Task Issue Type and Linking Model — Design Spec

- **Issue:** #358
- **Designed by:** @copilot
- **Date:** 2026-06-06
- **Status:** Draft

## Problem

PLATE currently has strong first-class issue types for implementation work (`Feature`, `Bug`), knowledge work (`Research`, `Question`, `Design`), and release/process artifacts (`Epic`, `Release`, `Audit`, `Migration`). It does **not** have a first-class artifact for work that only a human can perform, such as:

- creating or rotating credentials
- completing external paperwork or approvals
- updating DNS or cloud-console configuration
- performing one-off onboarding steps
- resolving blockers that an agent can identify but cannot safely execute

This creates a structural gap in the PLATE issue graph. Human-only blockers are currently forced into the wrong abstractions:

- `Question` is wrong because the unknown is not primarily informational
- `Feature` and `Bug` are wrong because the work is not implementation-first
- `Spike` is wrong because the work is not exploratory
- ad hoc comments or chat reminders are wrong because they are not durable GitHub artifacts

Epic #349 requires a first-class `Task` issue type so PLATE sessions can create durable, actionable human work items without pretending that the work is code or research.

## Constraints

- `Task` must be narrow: it is for **human-only blockers** and **explicitly requested human action items**, not a generic bucket for all manual follow-up.
- `Task` must fit the existing PLATE label-check and issue-template ecosystem with minimal ambiguity.
- `Task` must support both standalone use and linkage to existing artifacts such as Epics, Features, Questions, Bugs, and external prerequisites.
- `Task` must **not** require `Epic: <slug>` labeling, even when related to an Epic.
- When a `Task` is clearly Epic-related, it should inherit the Epic milestone.
- The closure model must support GitHub-native issue closure by a human or by the system after the human reports completion.
- Closure evidence must be lightweight and **must not** encourage secret leakage in comments.
- The design should stay aligned with the user's decisions captured on #358 and the scope boundaries on Epic #349.

## Design Decision

Introduce **`Task`** as a new first-class PLATE **issue type** for work that requires human intervention and cannot be safely completed by the agent.

### Core semantics

`Task` is used when **either** of these is true:

1. The user explicitly asks PLATE to create a human action item.
2. PLATE detects a blocker that clearly requires human intervention and has no safe agent-side workaround.

`Task` is **not** used for:

- generic reminders with no meaningful blocker or action requirement
- implementation work that belongs in `Feature` or `Bug`
- information gaps that belong in `Question` or `Research`
- exploratory work that belongs in `Spike`

### Taxonomy position

Add `Task` to the canonical PLATE issue-type taxonomy alongside `Bug`, `Feature`, `Epic`, `Release`, `Research`, `Design`, `Question`, `Audit`, and `Migration`.

This means follow-on implementation should update:

- `.github/labels.yml`
- `.github/workflows/label-check.yml`
- `.agentic/process.yml`
- root `AGENTS.md`
- any mirrored template payload copies that ship these rules downstream

### Relationship to other issue types

| Type | Primary purpose | Why it is not `Task` |
|---|---|---|
| `Question` | Capture an information goal that closes with an answer artifact | Questions resolve uncertainty; Tasks require a human action |
| `Research` | Gather and synthesize evidence | Research is evidence-first; Task is action-first |
| `Design` | Produce a design artifact or decision record | Design shapes future implementation; Task unblocks or performs human work |
| `Feature` | Deliver a product or operational capability | Features change repository behavior; Tasks often change external state |
| `Bug` | Correct broken behavior with reproduction + regression coverage | Bugs are defects in the system; Tasks often reflect external prerequisites |
| `Spike` | Time-box exploratory work | Spikes explore unknowns; Tasks request or record human action |

### Ownership and attachment model

`Task` can be either:

- **standalone** — when the action item is important but not clearly owned by an Epic or other issue, or
- **linked** — when it is created in response to an Epic, Feature, Bug, Question, or other artifact

#### Attachment rules

1. A `Task` does **not** require an `Epic: <slug>` label.
2. A `Task` **may** link to any relevant issue or artifact.
3. When a `Task` is clearly Epic-related, it should inherit the Epic milestone.
4. When it is not clearly Epic-related, milestone assignment is optional.

This makes `Task` different from `Feature`, which is Epic-owned by default, and from `Question`, which is intentionally standalone.

### Canonical linking model

Because GitHub's native issue-to-issue modeling is lightweight, the canonical contract should be:

1. **Body links first.** A Task includes a dedicated section linking the artifact(s) it blocks, depends on, or was created from.
2. **Milestone when clearly Epic-related.** This provides roll-up visibility without forcing `Epic:` labeling.
3. **Closing keywords only when a PR is actually involved.** If a repository change later resolves or supersedes the Task, a PR may link it with `Closes #N`. This is optional, not required.
4. **Comment provenance for agent-created Tasks.** When a Task is generated from a PLATE session, the creating surface should record where the need was detected (for example, the relevant issue, chat context, or failing operation), with best-effort redaction and summarization when the context appears sensitive.

Recommended body sections for a Task:

- **Human action required**
- **Why the agent cannot safely proceed**
- **Context and affected artifacts**
- **Best-effort instructions**
- **Done signal**
- **Related links**

### Required Task fields

Every `Task` template should require the following fields:

1. **Human action required** — the thing the human must do
2. **Why the agent cannot safely proceed** — the blocker or safety reason
3. **Context and affected artifacts** — what work, issue, workflow, deployment, or repo artifact this affects
4. **Best-effort instructions / next steps** — suggested path, explicitly not guaranteed correct
5. **Done signal** — how a human knows the Task is complete
6. **Links to blocking / related artifacts** — issues, docs, workflows, external consoles, or follow-up artifacts

Optional fields may include urgency/risk, owner, review date, or notes, but there is **no Task-specific urgency convention in v1**. Prioritization metadata can be added in later Task-prioritization work.

### Closure model

`Task` is the first PLATE issue type whose **normal** closure path is GitHub-native issue closure rather than a PR-backed git artifact.

#### Default closure path

1. A human completes the required action.
2. The human closes the Task issue directly **or** reports completion through a PLATE surface.
3. If completion is reported through PLATE, the system may post the completion comment and close the issue on the human's behalf.

#### Required closure evidence

Before closing, the Task should have a visible completion comment containing a lightweight structured marker:

`<!-- PLATE-TASK-CLOSED -->`

The marker should be accompanied by a short visible note. A minimal example is:

`Done — PAT created. <!-- PLATE-TASK-CLOSED -->`

However:

- the comment should describe the outcome when practical
- the comment must **not** include secrets, credentials, tokens, or privileged configuration values
- if completion changed repository truth, documentation, or process, a follow-up PR or documentation artifact may still be appropriate
- agent-created Tasks do **not** automatically require `need:human-review`; the `Task` type itself is sufficient default signal in v1

#### Impact on PLATE rules

This requires an explicit exception to the current Issue Artifact Rules, which presently state that every issue must close with a PR-backed git artifact.

Recommended rule change:

> `Task` issues close with a GitHub issue comment that includes `<!-- PLATE-TASK-CLOSED -->` and a short visible completion note. A PR or documentation artifact is required only when the completed task changes repository truth that should be committed.

This keeps operational human-only work first-class without forcing meaningless documentation PRs just to acknowledge a completed external action.

### Template and labeling implications

Follow-on implementation should add:

- a `Task` label in `.github/labels.yml`
- a dedicated `.github/ISSUE_TEMPLATE/task.yml`
- `Task` to the enforced issue-type list in `.github/workflows/label-check.yml`
- `Task` to issue-type and artifact tables in `AGENTS.md` and `.agentic/process.yml`
- `Task` to health/bootstrap required-label conventions

The template should clarify that:

- instructions are best effort
- the issue is for human-only work
- closure requires a completion comment containing `<!-- PLATE-TASK-CLOSED -->`
- Epic label inheritance is **not** required
- sensitive provenance should be redacted and summarized on a best-effort basis

### Interaction with existing templates

The existing `Migration task` template is a `Migration`-typed workflow artifact, not a general-purpose `Task`.

That distinction should remain:

- **Migration task** = subtype of `Migration`
- **Task** = first-class issue type for human-only blockers / requested actions

The UI naming is acceptable as long as the type labels remain unambiguous.

## Alternatives Rejected

| Alternative | Why Rejected |
|---|---|
| Reuse `Question` for human-only blockers | The work is not primarily an information goal; it is an action requirement |
| Reuse `Feature` or `Bug` for human tasks | These imply implementation/test/documentation expectations that do not fit external human actions |
| Require `Epic: <slug>` on all Task issues | Too rigid for cross-cutting or standalone human actions; contradicts the decisions captured on #358 |
| Make Task always standalone like `Question` | Loses useful Epic roll-up and milestone visibility when the task is clearly part of Epic delivery |
| Require a PR or docs artifact for every completed Task | Creates fake process work for real-world operational actions such as secret creation or DNS changes |
| Allow Task to cover any manual reminder or to-do | Too broad; would dilute the meaning of first-class human blockers |

## Artifact

This design defines the v1 contract for `Task` as:

- a new first-class PLATE issue type
- a dedicated issue template with six required fields
- a linkage model based on body links + optional milestone inheritance
- no required `Epic:` label
- GitHub-native direct closure with a minimum completion comment
- a narrow semantic scope: human-only blockers or explicitly requested human action items

### Proposed template outline

```markdown
name: Task
description: Track a human-only blocker or explicitly requested human action item.
title: "[Task]: "
labels:
  - Task
body:
  - human_action_required
  - why_agent_cannot_proceed
  - context_and_affected_artifacts
  - best_effort_instructions
  - done_signal
  - related_links
  - closing_requirements_checkbox
```

### Proposed AGENTS/process-table addition

| Issue Type | Required Git Artifact | Typical PR Type Label |
|---|---|---|
| `Task` | Completion comment on the GitHub issue; PR/doc artifact only when repository truth changes | `Documentation` when follow-up docs are needed, otherwise none |

## Open Questions

- Should v2 add a dedicated MCP/CLI closure helper for Tasks so the marker, redaction, and close action are applied consistently?
- Should future Task prioritization work introduce explicit urgency metadata, or continue relying on surrounding issue/project context?

## Acceptance Evidence

This design is implemented correctly when:

- `Task` exists as a first-class issue-type label and passes label-check enforcement
- a dedicated Task issue template exists with the required fields described above
- PLATE rules explicitly distinguish `Task` from `Question`, `Feature`, `Bug`, and `Spike`
- Task issues can be standalone or milestone-inheriting without requiring `Epic:` labels
- PLATE documentation explicitly permits GitHub-native closure comments for Tasks and requires the `<!-- PLATE-TASK-CLOSED -->` marker
- a PLATE session can later create Task issues that match this contract (#359, #360)
