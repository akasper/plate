# Conversation-to-Issue-Graph Schema and Mapping Rules — Design Spec

- **Issue:** #84
- **Designed by:** @copilot (agent session)
- **Date:** 2025-07-14
- **Status:** Draft

## Problem

When a PLATE agent guides a user through a planning session, it collects acceptance criteria, scope boundaries, unknowns, and dependency information through conversational Q&A. There is currently no canonical representation for what the agent has captured, and no deterministic rules for how that captured state maps to a set of PLATE-compliant GitHub issues. Without a shared schema and mapping rules, each agent session can produce a different issue structure, breaking traceability and PLATE gate compliance.

This design defines:

1. The **planning session intermediate representation** — the in-memory or serialised state the agent maintains during a session.
2. **Field extraction rules** — how each Q&A turn populates the session schema.
3. **Issue-type selection rules** — a decision tree for choosing Research / Design / Feature / Question / Spike.
4. **GitHub issue field mapping** — exact field values the agent writes when creating stubs.
5. **Progressive stub creation rules** — creation order and what deferred work `need:refinement` signals.
6. **Traceability requirements** — closing keywords, cross-references, and verification checks.
7. **Spike type definition** — full definition, gate behaviour, and required label changes.
8. **Session-to-issues idempotency** — safe re-entry when a session is interrupted.

## Constraints

- The agent must produce issues that pass the `label-check.yml` workflow, which requires exactly one PLATE issue type label and—for `Feature` and `Epic` issues—exactly one `Epic: <slug>` companion label.
- Agent-created stubs must include `Closes #<epic-number>` so the issue graph is navigable without external tooling.
- The schema must be serialisable (YAML/JSON) so that a PAUSED session can be resumed in a later conversation without losing state.
- Issue creation must be idempotent: running the same session twice must not create duplicate issues.
- The `Spike` issue type is new; its introduction requires coordinated additions to `labels.yml` and `label-check.yml`.
- Research artifacts produced by sessions MUST NOT be committed to `main` until reviewed; stub issues are sufficient at session-completion time.
- The planning session must not exceed 8 conversational turns (per `docs/research/interactive-planning-ux.md`): the schema must accommodate answers collected in a minimal 3-turn session.

## Design Decision

Adopt a single **`planning_session` document** as the canonical intermediate representation. The document is populated incrementally turn-by-turn and is the sole source of truth the agent uses when creating GitHub issues. Issue creation follows a strict dependency order (Epic → Research → Design → Feature/Spike) with idempotency checks at each step. A new `Spike` issue type is formally added to the PLATE label taxonomy.

## Alternatives Rejected

| Alternative | Why Rejected |
|---|---|
| Emit issues in real time as each Q&A turn completes | Creates partial issue sets if the session is interrupted; the Epic may not yet exist when child stubs are created. |
| Let the agent decide field values ad-hoc without a schema | Produces structurally inconsistent issues across sessions; breaks label-check CI. |
| Use a single monolithic issue with child task lists | GitHub task lists do not carry individual type labels, Epic labels, or closing keywords; PLATE traceability relies on discrete issues. |
| Map unknowns to `Question` instead of `Research` or `Spike` | `Question` issues require a single answerable information gap; compound unknowns that require evidence-gathering belong in `Research`; time-boxed exploration belongs in `Spike`. |

## Artifact

---

### 1. Planning Session Schema

The agent constructs and maintains the following document during a planning session. Fields are populated incrementally; incomplete fields carry the default values shown.

```yaml
planning_session:
  # Confirmed identity fields — populated in turns 1-2
  epic_name: string            # Required. Confirmed by user.
  problem_statement: string    # Required. Confirmed by user.

  # Extracted during Q&A — populated in turns 3-7
  acceptance_criteria: []      # List of strings. Extracted from user answers.
  in_scope: []                 # Confirmed in-scope items.
  out_of_scope: []             # Confirmed out-of-scope items.
  dependencies: []             # Upstream dependencies the user flagged.
  unknowns: []                 # Items classified as needing Research.
  design_areas: []             # Items classified as needing Design.
  features: []                 # Items classified as needing Feature implementation.
  spikes: []                   # Items flagged for Spike (time-boxed exploration).

  # Session lifecycle
  session_state: string        # BUILDING_EPIC | BUILDING_CHILDREN | COMPLETE | PAUSED
  github_epic_number: int      # Null until Epic issue is created.

  # Created issue registry — populated during issue-creation phase
  child_issues: []             # List of {number: int, type: string, title: string}.
```

#### `session_state` transitions

```
BUILDING_EPIC
    │  (epic_name and problem_statement confirmed)
    ▼
BUILDING_CHILDREN
    │  (all stubs created)
    ▼
COMPLETE

Any state ──► PAUSED  (user ends session; serialise document)
PAUSED      ──► BUILDING_EPIC | BUILDING_CHILDREN  (session resumed)
```

---

### 2. Field Extraction Rules

The table below maps each planning-session Q&A turn to the schema fields it populates and the language patterns that trigger each classification.

| Turn | Question asked by agent | Fields populated | User language patterns | Default when skipped |
|---|---|---|---|---|
| 1 | "What are we building? Give me a name and one-sentence description." | `epic_name`, `problem_statement` | Any noun phrase accepted as `epic_name`; the description sentence becomes `problem_statement`. | Agent must re-ask; these fields are required. |
| 2 | "What does done look like? List the outcomes you need." | `acceptance_criteria` | Numbered list, bulleted list, or run-on "and" sentences — split on `;`, `,`, or `and then`. | `["TBD — to be refined"]` |
| 3 | "What is definitely in scope? What is definitely out of scope?" | `in_scope`, `out_of_scope` | "in scope: …" / "we will …" → `in_scope`; "not in scope" / "we won't" / "out of scope" / "explicitly excluding" → `out_of_scope`. | Both default to `[]`; agent annotates as `assumed-default`. |
| 4 | "Are there upstream systems, teams, or decisions this depends on?" | `dependencies` | "we need X first" / "blocked by" / "requires" / "depends on" / "waiting for" → `dependencies`. | `[]` |
| 5 | "What do we not know yet?" | `unknowns`, `spikes` | "we don't know" / "unclear" / "TBD" / "need to figure out" → `unknowns`; "no idea how to approach" / "could go several ways" / "genuinely uncertain about the approach" → `spikes`. | `[]` |
| 6 | "Are there areas that need a design decision before anyone writes code?" | `design_areas` | "need a design" / "should be designed" / "architecture decision" / "UX decision" / "API contract" / "data model" → `design_areas`. | `[]` |
| 7 | "What are the concrete things to build once unknowns are resolved?" | `features` | "build X" / "implement Y" / "add Z" / "create W" → `features`. Items already covered by `design_areas` or `spikes` are excluded. | `[]` |
| 8 (optional) | "Anything else? Shall I proceed?" | Any field | Catch-all; the agent re-classifies any new items and confirms the full summary before creating issues. | Session closes with current state. |

#### Fast-path behaviour (≤ 3 turns)

When a user provides a very short reply (< 6 words) or says "let's just go with that" / "skip" / "just start", the agent MUST:

1. Scaffold all remaining unanswered fields with their defaults.
2. Annotate each scaffolded field with `# assumed-default` in the serialised document.
3. Present a one-paragraph summary and proceed on the user's single confirmation.

The `need:refinement` label on child stubs signals that scaffolded defaults are present and human review is expected.

---

### 3. Issue-Type Selection Rules

Use the following decision tree for every item collected in the session.

```
Is the item a concrete, scoped requirement ready for implementation?
├─ YES → Is the approach known and non-exploratory?
│         ├─ YES → Feature
│         └─ NO  → Is the unknowing time-bounded and approach-exploratory?
│                   ├─ YES → Spike
│                   └─ NO  → Research (if information-gathering), Design (if decision-making)
└─ NO  → Is it an information gap answerable in a single Q&A exchange?
          ├─ YES → Question
          └─ NO  → Does it require external evidence, comparison, or source research?
                    ├─ YES → Research
                    └─ NO  → Design (if it requires a UX, API, or architecture decision)
```

#### Type definitions

| Type | Definition | Prerequisite |
|---|---|---|
| **Research** | An unknown that requires information-gathering (literature, benchmarking, comparative analysis, source inspection) before implementation is possible. Produces a findings document. | The question cannot be answered from existing team knowledge in a single conversation. |
| **Design** | A known requirement that needs a UX, API, or architecture decision before code is written. Produces a design artifact in `docs/design/`. | The requirement is understood but the solution shape is not. |
| **Feature** | A known, scoped requirement ready for implementation. No open design or research blockers. | Acceptance criteria are present; approach is agreed. |
| **Question** | A specific information gap answerable in a single Q&A session. Closes with a documented answer, not a code change. | The gap is narrow and the answer signal is clear (see issue template). |
| **Spike** | A time-boxed exploration task; used when the approach is genuinely unknown and a Feature would be premature. Produces findings committed to `docs/research/`. | The approach space is open-ended; a Feature would require assumptions not yet validated. |

#### When to prefer Spike over Research

Use **Spike** when:

- The team knows the question but cannot estimate the implementation size until they try something.
- The work requires a proof-of-concept, a throwaway implementation, or direct tool evaluation to produce a useful answer.
- The output is an exploration result (what we learned), not a literature survey or comparative analysis.
- A fixed timebox (e.g. 2–4 hours) is appropriate as a stopping condition.

Use **Research** when:

- The work primarily involves reading external sources, comparing alternatives, or synthesising knowledge.
- No code is written (or code is only illustrative examples, not working prototypes).
- The output is a structured findings document that other issues cite as a prerequisite.

A single Q&A can produce both: a `Research` stub for background knowledge-gathering and a `Spike` stub for hands-on exploration of a specific approach.

---

### 4. GitHub Issue Field Mapping

The agent populates the following fields exactly as specified. Cells marked `{variable}` are substituted from the session schema.

| Field | Epic | Research stub | Design stub | Feature stub | Spike stub |
|---|---|---|---|---|---|
| **title** | `[Epic] {epic_name}` | `Research: {topic}` | `Design: {area}` | `Feature: {capability}` | `Spike: {question}` |
| **body** | See §4.1 | See §4.2 | See §4.3 | See §4.4 | See §4.5 |
| **labels** | `Epic`, `Epic: {slug}` | `Research`, `Epic: {slug}` | `Design`, `Epic: {slug}` | `Feature`, `Epic: {slug}`, `need:refinement` | `Spike`, `Epic: {slug}`, `need:refinement` |
| **closing keyword** | n/a (Epic is the root) | `Closes #{epic_number}` | `Closes #{epic_number}` | `Closes #{epic_number}` | `Closes #{epic_number}` |
| **milestone** | Set if session includes target release | Inherit from Epic | Inherit from Epic | Inherit from Epic | Inherit from Epic |

The `{slug}` for the `Epic: {slug}` label is derived from `epic_name`: lower-cased, spaces replaced with hyphens, special characters stripped, truncated at 40 characters. Example: `"User Onboarding Flow"` → `Epic: user-onboarding-flow`.

> **Label-check compliance:** The `Spike` label must be added to `labels.yml` and to the `issueTypeLabels` array in `label-check.yml` before any Spike issues are created (see §7).

#### 4.1 Epic body template

```markdown
## Problem

{problem_statement}

## Acceptance Criteria

{acceptance_criteria as numbered list}

## In Scope

{in_scope as bulleted list, or "TBD — see child issues"}

## Out of Scope

{out_of_scope as bulleted list, or "None identified"}

## Dependencies

{dependencies as bulleted list, or "None identified"}

## Child Issues

<!-- PLATES-CHILDREN: appended by agent after all stubs are created -->
```

#### 4.2 Research stub body template

```markdown
## Research Question

{item text from session unknowns[]}

## Context

Part of epic: #{epic_number} — {epic_name}

<!-- PLATES-EPIC: #{epic_number} -->

## Success Condition

A findings document committed to `docs/research/` that answers the question above.

Closes #{epic_number}
```

#### 4.3 Design stub body template

```markdown
## Design Scope

{item text from session design_areas[]}

## Constraints

(To be identified during refinement.)

## Context

Part of epic: #{epic_number} — {epic_name}

<!-- PLATES-EPIC: #{epic_number} -->

## Success Condition

A design artifact committed to `docs/design/` or `docs/adr/` that resolves the design question above.

Closes #{epic_number}
```

#### 4.4 Feature stub body template

```markdown
## Summary

{item text from session features[]}

## Acceptance Criteria

{acceptance_criteria subset applicable to this feature, or "To be refined — see Epic #{epic_number}"}

## Context

Part of epic: #{epic_number} — {epic_name}

<!-- PLATES-EPIC: #{epic_number} -->

Closes #{epic_number}
```

#### 4.5 Spike stub body template

```markdown
## Exploration Question

{item text from session spikes[]}

## Timebox

{timebox_estimate, default: "2–4 hours — to be confirmed during refinement"}

## Success Condition

(What answer ends the spike — to be filled during refinement.)

## Context

Part of epic: #{epic_number} — {epic_name}

<!-- PLATES-EPIC: #{epic_number} -->

Closes #{epic_number}
```

---

### 5. Progressive Stub Creation Rules

#### Creation order

```
1. Epic issue
2. Research stubs  (one per unknowns[] item)
3. Design stubs    (one per design_areas[] item)
4. Feature stubs   (one per features[] item)
5. Spike stubs     (one per spikes[] item)
```

Research and Design stubs are created before Feature and Spike stubs because Feature/Spike issues may reference or depend on the Research/Design work. This order also makes the resulting issue list naturally sorted by prerequisite dependency.

#### Required fields at stub creation time

| Issue Type | Required at creation | Deferred to refinement |
|---|---|---|
| Epic | `title`, `body` (problem + AC skeleton), `Epic` label, `Epic: {slug}` label | Milestone, final AC, `## Child Issues` section (appended after children created) |
| Research | `title`, `body` (question + context), `Research` label, `Epic: {slug}` label, `Closes #epic` | Detailed scope, methodology, assigned researcher |
| Design | `title`, `body` (scope + context), `Design` label, `Epic: {slug}` label, `Closes #epic` | Constraints, artifact format, assigned designer |
| Feature | `title`, `body` (summary + context), `Feature` label, `Epic: {slug}` label, `need:refinement`, `Closes #epic` | Full AC, test plan, CURRENT.md update |
| Spike | `title`, `body` (question + timebox placeholder + context), `Spike` label, `Epic: {slug}` label, `need:refinement`, `Closes #epic` | Timebox confirmation, success condition, assignee |

#### `need:refinement` semantics

`need:refinement` signals that the following PLATE gates are **deferred** until a human reviews the stub:

- Acceptance-criteria completeness check (the AC may be a placeholder or inherited from the Epic).
- `CURRENT.md` update (Feature issues only — not required until implementation begins).
- Timebox and success condition (Spike issues only).

The following PLATE requirements are **always enforced** even on `need:refinement` stubs:

- Exactly one issue type label (`Feature`, `Spike`, etc.).
- Exactly one `Epic: {slug}` label.
- `Closes #{epic_number}` closing keyword in the body.

The `need:refinement` label is removed by a **human** after they have reviewed and completed the stub. Agents do not self-remove `need:refinement`; they may add it and may check for its presence but must not unilaterally strip it.

---

### 6. Traceability Requirements

#### Closing keyword requirement

Every child issue body MUST contain either:

- `Closes #{epic_number}` (preferred) — creates a native cross-reference in the Epic timeline. **Note:** GitHub only processes closing keywords in PR bodies and commit messages, not in issue bodies. When placed in a child issue body, this keyword serves as (1) a navigation cross-reference and (2) a template hint — agents and humans implementing the child issue should copy this keyword into the implementing PR body, where GitHub will then automatically close the issue when the PR merges to the default branch. **OR**
- `<!-- PLATES-EPIC: #{epic_number} -->` — used only when the issue does not directly close the Epic (e.g. a Research stub whose findings feed a Design issue that closes the Epic). The HTML comment preserves machine-readable traceability even if GitHub's cross-reference is absent.

Both forms may coexist. The preferred pattern for most stubs is the `Closes` keyword.

#### Agent verification before marking a stub complete

Before recording an issue number in `child_issues[]`, the agent MUST:

1. Read the issue body from the GitHub API response.
2. Confirm that either `Closes #{epic_number}` or `<!-- PLATES-EPIC: #{epic_number} -->` appears in the body.
3. Confirm that the issue carries exactly one PLATE type label and exactly one `Epic: {slug}` label.
4. If either check fails, update the issue before recording it.

#### Epic `## Child Issues` section

After all child stubs are created, the agent appends the following section to the Epic body (replacing any existing `<!-- PLATES-CHILDREN: ... -->` placeholder):

```markdown
## Child Issues

| # | Type | Title |
|---|---|---|
| #{number} | Research | Research: {topic} |
| #{number} | Design   | Design: {area} |
| #{number} | Feature  | Feature: {capability} |
| #{number} | Spike    | Spike: {question} |
```

The append is an edit to the Epic issue body via `gh issue edit --body`. The agent reads the current body, locates the `<!-- PLATES-CHILDREN: ... -->` marker or the end of the body, and replaces or appends the table. The operation is idempotent: if the section already exists, the agent overwrites it with the current `child_issues[]` list.

---

### 7. Spike Type Definition

#### What Spike is

A **Spike** is a time-boxed, goal-directed exploration issue. It is used when the team knows what question needs answering but does not yet know how to approach the implementation. A Spike authorises a bounded investigation; it is not a research survey (that is `Research`) and not an implementation task (that is `Feature`).

The term originates from Extreme Programming, where a spike is a throwaway experiment written to reduce risk or uncertainty before committing to a solution.

#### When to use Spike

- The implementation approach is unknown and a Feature estimate would be fiction.
- A working prototype, benchmark, or hands-on tool evaluation is the most effective way to answer the question.
- The team agrees to a fixed time budget after which a decision is made regardless of outcome.

#### PLATE gate behaviour for Spike issues

| Gate | Behaviour |
|---|---|
| Label check | Must carry `Spike` label + `Epic: {slug}` label. `Spike` must appear in `issueTypeLabels` in `label-check.yml`. |
| Closing artifact | Findings document committed to `docs/research/<slug>.md`. |
| PR type label | `Documentation` (findings are docs, not shipping code). |
| Closing keyword | PR body must include `Closes #{spike_issue_number}`. |
| `CURRENT.md` update | Not required (Spike output is a research artifact, not a behaviour change). |
| `need:refinement` removal | Human removes after confirming timebox, success condition, and assignee are complete. |

#### Required Spike issue fields

| Field | Requirement |
|---|---|
| Title | MUST begin with `Spike:` prefix (e.g. `Spike: evaluate auth library options`). |
| Timebox estimate | MUST appear in the issue body. If unknown at stub creation, use placeholder `"2–4 hours — to be confirmed during refinement"`. |
| Exploration question | MUST state what specific question the spike answers. |
| Success condition | MUST state what answer or output ends the spike. May be placeholder at stub creation; must be filled before work starts. |
| `Closes` keyword | MUST reference the parent Epic: `Closes #{epic_number}`. |

#### Required label changes

To support `Spike` issues, two repository files must be updated in the same PR that introduces the first Spike issue (or in a preparatory PR):

**`labels.yml`** — add:

```yaml
- name: "Spike"
  color: "e4e669"
  description: "Issue type: time-boxed exploration task to reduce implementation uncertainty."
```

**`label-check.yml`** — update `issueTypeLabels`:

```js
const issueTypeLabels = ['Bug', 'Feature', 'Epic', 'Research', 'Design', 'Question', 'Audit', 'Migration', 'Feedback Response', 'Spike'];
```

Until these changes are merged and the `Spike` label is created on GitHub, the agent MUST NOT create Spike issues. Instead it should note in the session summary that Spike stubs are deferred pending label provisioning.

---

### 8. Session-to-Issues Idempotency

#### Interrupted session recovery

If a session is interrupted after partial issue creation, the agent follows this recovery procedure on re-entry:

1. **Deserialise** the saved `planning_session` document (from session memory or from a comment on the Epic issue).
2. **Inspect `child_issues[]`**: for each entry, verify the issue still exists on GitHub via `gh issue view #{number}`.
3. **Identify missing stubs**: compare `child_issues[]` against the full expected set derived from `unknowns[]`, `design_areas[]`, `features[]`, and `spikes[]`. Any item without a corresponding `child_issues[]` entry is missing.
4. **Create missing stubs only**: do not re-create issues that already exist.
5. **Update the Epic `## Child Issues` section** after recovery is complete.

#### Duplicate detection

Before creating any stub, the agent searches for an existing issue that matches both criteria:

1. Title matches the expected prefix pattern (e.g. `Research: {topic}` — exact string match, case-insensitive).
2. Issue carries the `Epic: {slug}` label for the current epic.

Search command:

```bash
gh issue list \
  --repo {owner}/{repo} \
  --label "Epic: {slug}" \
  --state all \
  --search "in:title \"{expected_title_prefix}\""
```

If a matching issue is found, the agent records its number in `child_issues[]` and skips creation. If no match is found, the agent creates the issue and records the returned number.

#### Session document persistence

The agent persists the serialised `planning_session` document by embedding it in a paired HTML comment block in the Epic issue body immediately after the Epic is created:

```html
<!-- PLATE_SESSION_STATE -->
{yaml_document}
<!-- /PLATE_SESSION_STATE -->
```

This makes the session state part of the durable GitHub record. On re-entry, the agent reads the Epic issue body, extracts the `<!-- PLATE_SESSION_STATE -->...<!-- /PLATE_SESSION_STATE -->` block, and deserialises it. Updates to the session document (new child issues, state transitions) are written back to this block via `gh issue edit`.

---

## Open Questions

| # | Question | Suggested resolution |
|---|---|---|
| OQ-1 | Should Research and Design stubs that block Feature stubs express that blocking relationship via GitHub's native blocker feature? | Yes, if the project has PLATE's blocker workflow enabled (sets `status:blocked` / `status:ready-to-work`). The agent should add blockers only when `PLATE_BLOCKERS_ENABLED` is set. Needs a follow-up Feature issue. |
| OQ-2 | How should the agent handle a session where the user provides no `unknowns`, no `design_areas`, and no `features` — only the Epic identity? | Create the Epic stub with `need:refinement` and a comment asking the user to enumerate child work items in a follow-up session. Do not create child stubs. |
| OQ-3 | Is the `<!-- PLATE_SESSION_STATE -->` block safe from accidental human editing that would corrupt YAML? | Consider a checksum or version field in the YAML header. Needs a follow-up design decision. |
| OQ-4 | Should the `Spike` label colour `e4e669` (yellow) be differentiated from `Feedback Response` which uses the same colour? | The two types have distinct enough names; colour collision is acceptable short-term. Revisit if the label UI becomes confusing. |

## Acceptance Evidence

This design is considered implemented when:

1. An agent session can produce a `planning_session` document from a ≤ 8-turn Q&A exchange and create a PLATE-compliant issue graph (Epic + child stubs) that passes `label-check.yml` on every created issue.
2. The `Spike` label exists in `labels.yml`, is registered in `label-check.yml`, and a Spike issue created by the agent passes the label check.
3. Re-running the issue-creation phase on an already-complete session produces no new GitHub issues (idempotency verified by the duplicate-detection search).
4. Every child issue body contains either `Closes #{epic_number}` or `<!-- PLATES-EPIC: #{epic_number} -->`.
5. The Epic issue body's `## Child Issues` section is accurate and complete after session completion.
