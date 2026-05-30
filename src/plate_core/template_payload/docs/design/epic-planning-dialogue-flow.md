# Epic Planning Dialogue Flow — Design Spec

- **Issue:** #83
- **Designed by:** @copilot
- **Date:** 2026-05-26
- **Status:** Draft

## Problem

The PLATE agent needs a well-defined, user-friendly conversation flow for the opt-in interactive epic planning mode. Without a specified dialogue state machine and exact prompt wording, different agent sessions produce inconsistent experiences: some sessions skip the opt-in gate, some create duplicate Epics, and incomplete sessions leave the Epic issue body empty. This design specifies the full conversation as a testable state machine with exact prompt strings, incremental update behaviour, and graceful degradation paths.

## Constraints

- The agent must never create a GitHub issue without explicit user confirmation (PLATE autopilot doctrine: humans keep judgment).
- Total Q&A turns must not exceed 8 (research finding from `docs/research/interactive-planning-ux.md` §1).
- The Epic issue must be created once, and only once, and only after both a name and a problem statement have been confirmed by the user.
- All state must be persisted to the GitHub issue body after each Q&A turn so that session resumption works without in-process memory.
- The agent must never push directly to `main`.
- Duplicate-Epic detection must run before any HIGH-confidence confirmation prompt fires (research finding from `docs/research/epic-intent-detection.md` §4).

## Design Decision

Model the planning conversation as an explicit finite-state machine with eight primary states. Transitions carry guard conditions derived from the intent-detection confidence heuristic (§2 of the intent-detection research). State is checkpointed into the Epic issue body after every mutation, enabling resumption from any point. The confirmation prompt is always opt-in, single-sentence, and specific about what will be created.

## Alternatives Rejected

| Alternative | Why Rejected |
|---|---|
| Always-on planning mode (no opt-in) | Violates autopilot doctrine; users who mention an Epic topic conversationally would receive unsolicited issue creation. |
| Single long form prompt (all questions at once) | Research shows users perceive this as a form; drop-off rate increases sharply after turn 6 (Lux et al., CHI '22 cited in UX research). |
| Storing session state in-process only | Any agent restart loses state; persisting to the issue body is the only durable store available. |
| Creating child issues before the Epic exists | Orphaned child issues have no parent label and cannot be traced back; Epic must exist first. |
| Blocking on vague answers indefinitely | Research recommends at most two escalation attempts per dimension before defaulting (UX research §5). |

## Artifact

### 1. State Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         EPIC PLANNING STATE MACHINE                         │
└─────────────────────────────────────────────────────────────────────────────┘

                          ┌──────────┐
                          │  IDLE    │
                          └────┬─────┘
                               │ Signal detected (score ≥ 5 HIGH,
                               │ or two MEDIUM in ≤ 3 turns)
                               ▼
                    ┌──────────────────────┐
                    │  SIGNAL_DETECTED     │◄──── Re-evaluate after each turn
                    └──────────┬───────────┘      while score is MEDIUM (3-4)
                               │
                               │ Run duplicate-Epic check
                               │ (gh issue list --label Epic --state open)
                               │
               ┌───────────────┴───────────────┐
               │ Jaccard ≥ 0.4 OR              │ No overlap
               │ label-slug match              │ (Jaccard < 0.4)
               ▼                               ▼
   ┌───────────────────────┐       ┌───────────────────────────┐
   │  DUPLICATE_WARNING    │       │   AWAITING_CONFIRMATION   │
   └───────────┬───────────┘       └─────────────┬─────────────┘
               │                                 │
   ┌───────────┼───────────┐        ┌────────────┼────────────┐
   │           │           │        │            │            │
   ▼           ▼           ▼        ▼            │            ▼
Use        Create       Cancel    Confirmed      │         Declined
existing   new Epic     entirely  (user says     │         ("no", "not now",
Epic ──►   anyway ──►   ──►       yes/proceed)   │          silence + 1 turn)
   │           │      ABANDONED                  │              │
   │           │                                 │              ▼
   │           └──────────────────────┐          │           IDLE
   │                                  │          │
   └──────────────────────────────────┴──────────┘
                                      │
                                      ▼
                            ┌──────────────────┐
                            │  PLANNING_MODE   │
                            │  (Q&A session)   │
                            └────────┬─────────┘
                                     │
                                     │ User provides name + problem statement
                                     │ (Minimum Threshold Gate — see §3)
                                     ▼
                            ┌──────────────────┐
                            │  BUILDING_EPIC   │
                            │  gh issue create │
                            └────────┬─────────┘
                                     │ Epic issue created; body stub written
                                     ▼
                            ┌──────────────────┐
                            │ BUILDING_CHILDREN│◄─── Incremental Q&A turns
                            │  (turns 4–8)     │     edit Epic body after each
                            └────────┬─────────┘
                                     │
                     ┌───────────────┴───────────────┐
                     │ All arcs done OR user signals  │ User explicitly
                     │ "that's enough" / turn 8       │ cancels mid-session
                     ▼                               ▼
                ┌──────────┐                   ┌──────────────┐
                │ COMPLETE │                   │  ABANDONED   │
                └──────────┘                   └──────────────┘
```

**Guard conditions summary**

| Transition | Guard |
|---|---|
| IDLE → SIGNAL_DETECTED | Intent score ≥ 3 (MEDIUM) |
| SIGNAL_DETECTED → AWAITING_CONFIRMATION | Score ≥ 5 (HIGH), OR two MEDIUM signals in ≤ 3 turns on the same topic |
| SIGNAL_DETECTED → DUPLICATE_WARNING | HIGH confidence AND duplicate check returns Jaccard ≥ 0.4 or label-slug overlap |
| AWAITING_CONFIRMATION → PLANNING_MODE | User affirmative response ("yes", "sure", "let's do it", "go ahead", or equivalent) |
| AWAITING_CONFIRMATION → IDLE | User declines ("no", "not now", "just thinking out loud") or gives no response for one additional turn |
| DUPLICATE_WARNING → PLANNING_MODE | User says "something different" / "create new anyway" |
| DUPLICATE_WARNING → PLANNING_MODE (existing) | User says "work within existing" / "use that one" |
| DUPLICATE_WARNING → ABANDONED | User says "cancel" / "never mind" |
| PLANNING_MODE → BUILDING_EPIC | User has provided both name and problem statement (minimum threshold met) |
| BUILDING_EPIC → BUILDING_CHILDREN | `gh issue create` succeeds; Epic issue number assigned |
| BUILDING_CHILDREN → COMPLETE | All Q&A arcs closed, OR turn 8 reached, OR user says "that's enough" |
| BUILDING_CHILDREN → ABANDONED | User says "stop", "cancel", "forget it" |

---

### 2. Detection → Confirmation Phase

#### 2.1 Signal Detection to Opt-In Prompt

When the intent-detection scoring heuristic (defined in `docs/research/epic-intent-detection.md` §2) produces a HIGH score (≥ 5 points), the agent:

1. Runs the duplicate-Epic check (§7 below) before doing anything else.
2. Based on the duplicate check result, selects one of three prompt templates (§2.2).
3. Sends exactly one confirmation prompt. Does not create any issue or draft until the user confirms.
4. Waits for one turn. If the user neither confirms nor declines within that turn, treats silence as a soft decline and transitions back to IDLE.

The agent must not prompt more than once per topic per session. If the user declines or ignores the prompt, the topic is recorded internally as "user showed interest, declined to plan" and the agent does not re-prompt.

#### 2.2 Exact Confirmation Prompts

**Scenario A — New Epic (no duplicate found, HIGH confidence)**

> "It sounds like you're thinking about building [X]. Want me to kick off an Epic for that — scope, success criteria, and child feature breakdown?"

*[X] is the noun phrase extracted from the user's utterance.*

**Scenario B — Possible or Strong Duplicate**

Strong duplicate (Jaccard ≥ 0.6 OR exact label match):

> "Before creating a new Epic, I noticed **[Epic: slug-name](#N)** is already open and covers some of this ground ([1–2 overlapping domain nouns]). Is your request distinct from that scope, or should we work within that existing Epic?"

Possible overlap (Jaccard 0.4–0.6 OR label-slug shares ≥ 2 tokens):

> "There might be some overlap with **[Epic: slug-name](#N)** — want me to check if this fits there or if it's distinct enough for its own Epic?"

**Scenario C — Browsing / Exploratory (MEDIUM confidence, not yet HIGH)**

> "Happy to think through [X] with you. If at any point you'd like to turn this into a tracked Epic, just say the word."

*This prompt does not wait for confirmation. It is purely informational and plants a forward path.*

#### 2.3 If the User Declines

> "Got it — no problem. I'll leave that as a discussion for now. Let me know if you want to revisit it."

Actions:
- Clear the confidence state for this topic.
- Do not re-prompt for this topic in the session.
- Continue responding to whatever the user's actual question was.
- Transition to IDLE.

---

### 3. Minimum Threshold Gate

The agent may only call `gh issue create` once the user has explicitly provided **both**:

1. **Name** — a short title or noun phrase for the Epic (e.g., "Notification System", "Auth Overhaul").
2. **Problem Statement** — one or more sentences describing the problem being solved or the job-to-be-done.

#### 3.1 Extraction and Confirmation

The agent derives the name from the topic noun phrase in the confirmation prompt. After the user confirms, the agent immediately asks for the problem statement if it was not already provided:

> "Great — what problem does the [name] Epic solve, or what should a user be able to do when it's working?"

If the user's confirmation message itself contains a problem statement (e.g., "yes, users can't currently log in without refreshing"), the agent extracts it directly without asking again.

The agent reflects both fields back before creating:

> "I'll create an Epic titled **[name]** for the problem: *[problem statement]*. Ready to create the issue?"

If the user amends either field, the agent updates and reflects once more. After one correction cycle, it proceeds on the user's most recent statement.

#### 3.2 Epic Issue Fields at Creation Time

```
gh issue create \
  --title "[Epic] [name]" \
  --body  "## Problem\n[problem statement]\n\n## Acceptance Criteria\n\n_To be filled during planning session._\n\n## Scope\n\n_To be filled during planning session._\n\n## Out of Scope\n\n_To be filled during planning session._\n\n## Dependencies\n\n_To be filled during planning session._\n\n## Session State\n\n<!-- PLATE_SESSION_STATE -->\nphase: planning_mode\nlast_step: threshold_gate\nchild_issues: []\n<!-- /PLATE_SESSION_STATE -->" \
  --label "Epic" \
  --label "Epic: [epic-slug]" \
  --label "need:refinement"
```

Fields set at creation:
- **Title:** the confirmed name
- **Body:** stub sections for Acceptance Criteria, Scope, Out of Scope, Dependencies, and a machine-readable `PLATE_SESSION_STATE` block
- **Labels:** `Epic`, `Epic: [epic-slug]`, `need:refinement`

---

### 4. Q&A Phase — Acceptance Criteria + Scope

Total turn budget: **8 turns maximum** across the entire planning session (research finding). The agent tracks turns starting from PLANNING_MODE entry.

#### 4.1 Acceptance Criteria Arc (turns 1–3)

**Turn 1 — Opening framing question**

> "What should a user be able to do, or what should happen, when [name] is working correctly?"

Purpose: anchors the user in outcomes, not implementation. Allows any level of detail.

**Turn 2 — Specificity-probing follow-up**

> "You said [paraphrase of their answer]. What would I see or measure that tells me that's happening correctly?"

Variants for common vague answers:
| User says | Agent probes |
|---|---|
| "It should work well" | "What does 'working well' look like in the worst realistic case?" |
| "It should be fast" | "Fast compared to what? Is there a threshold that would make it unacceptable?" |
| "It should be easy to use" | "If a new user tried this without instructions, what would you expect them to get right on the first try?" |
| "It should handle errors" | "Walk me through what should happen the first time an error occurs." |

**Turn 3 — "Done means…" closure**

> "Let me reflect back what I've heard: done means [summary of turns 1–2]. Does that capture it, or is there anything missing?"

This is a confirmation step, not a new question. The output is a committed acceptance criterion. If the user amends, the agent incorporates the amendment and confirms once more. After two amendment cycles, the agent scaffolds a criterion marked `[needs-review]` and moves on.

After turn 3, the agent edits the Epic issue body (§5) and posts:
> "📝 Updated #[N] with acceptance criteria."

#### 4.2 Scope Boundary Arc (turns 4–6)

**Turn 4 — In-scope confirmation (restatement)**

> "Based on what you've described, I think the scope includes: [3–5 item list derived from prior turns]. Does that match what you had in mind?"

**Turn 5 — Out-of-scope guard**

> "Is there anything this should explicitly not do, or a closely related problem it should leave for another time?"

If the user says "I'm not sure" or does not answer: scaffold a placeholder:
> "I'll note that related items like [X] are not included in this work. Let me know if that changes."

**Turn 6 — Dependency flag**

> "Does this depend on anything that isn't built yet, or on a decision that hasn't been made?"

If the user names a dependency, record it in the `## Dependencies` section. Do not attempt to resolve the dependency within the session.

After each of turns 4–6, the agent edits the Epic body (§5) and posts the update confirmation message (§5.3).

#### 4.3 Incremental Update After Each Answer

After each accepted answer in turns 1–6, the agent:
1. Edits the Epic issue body to append/replace the relevant section (§5).
2. Updates the `PLATE_SESSION_STATE` block to record which step was last completed.
3. Posts a brief update confirmation to the user (§5.3).

#### 4.4 Fast-Path Detection

If the user signals they want to move faster (short replies < 6 words, "let's just go with that", "that's fine", explicit "skip"/"move on"/"just start"):
- Collapse remaining questions into a single summary-and-confirm: "Here's what I have so far — want me to proceed with this?"
- Scaffold all remaining unknowns as defaults, marked `[assumed]` in the issue body.
- Do not penalise speed; a fast session produces the same artifact with more `[assumed]` annotations.

---

### 5. Incremental Issue Update Pattern

#### 5.1 Update Trigger

After each user answer that advances a Q&A step, the agent calls `gh issue edit` before sending its next message to the user. The issue body is always the primary source of truth.

#### 5.2 Exact Body Sections Updated

| Q&A Step | Section Updated | Content Written |
|---|---|---|
| Turn 3 (AC closure) | `## Acceptance Criteria` | The confirmed acceptance criterion, or `[needs-review]` if vague. |
| Turn 4 (scope confirm) | `## Scope` | Bulleted list of in-scope items confirmed by the user. |
| Turn 5 (out-of-scope) | `## Out of Scope` | Bulleted list of explicitly excluded items; `[assumed: not included]` for scaffolded placeholders. |
| Turn 6 (dependency flag) | `## Dependencies` | Named dependencies as `- [dependency: X]`; empty if none stated. |
| Every turn | `PLATE_SESSION_STATE` block | `last_step` updated to current step name; `child_issues` list updated when stubs are created. |

The `PLATE_SESSION_STATE` block is an HTML comment block embedded in the issue body:

```markdown
<!-- PLATE_SESSION_STATE -->
phase: building_children
last_step: out_of_scope
child_issues: [101, 102]
<!-- /PLATE_SESSION_STATE -->
```

This block is machine-readable and used for session resumption (§8). It must not be removed or edited by hand.

#### 5.3 User-Facing Update Signal

After each `gh issue edit` call, the agent sends:

> "📝 Updated #[N] with your answer."

Where `[N]` is the Epic issue number. This is always the last line of the agent's turn, after any substantive content.

---

### 6. Progressive Child-Issue Creation

Child issues are proposed and created in the BUILDING_CHILDREN state, after the Epic issue exists and at least the acceptance criteria arc is complete (turn 3+).

#### 6.1 Creation Order

The agent proposes child stubs in this order: **Research → Design → Feature**. Each type is only proposed if it is relevant to the Epic.

The agent announces each before creating:

> "I'd like to create a Research stub for [specific aspect] — does that sound right?"

After user confirms (or after a fast-path signal):

> "Created **Research: [title]** as #[N]. 🔬"  
> "Created **Design: [title]** as #[N]. 📐"  
> "Created **Feature: [title]** as #[N]. ✨"

#### 6.2 Child Issue Fields at Creation

```
gh issue create \
  --title "[type]: [descriptive title]" \
  --body  "## Problem\n[problem statement copied from Epic]\n\n## Parent Epic\nCloses #[Epic N]\n\n## Notes\n_Stub created during Epic planning session. Needs refinement._" \
  --label "[Research|Design|Feature]" \
  --label "Epic: [epic-slug]" \
  --label "need:refinement"
```

Fields set at child creation:
- **Title:** `[Type]: [descriptive title]`
- **Body:** Problem statement copied from Epic body, parent Epic reference, stub note
- **Labels:** issue-type label (`Research`, `Design`, or `Feature`), `Epic: [slug]`, `need:refinement`

After each child is created, the agent updates the Epic body's `PLATE_SESSION_STATE` block with the new issue number.

---

### 7. Duplicate-Epic Warning Flow

#### 7.1 Trigger Condition

Before presenting the Scenario A confirmation prompt, the agent runs:

```sh
gh issue list --label Epic --state open --json number,title,labels,body
```

A duplicate warning is triggered when any open Epic meets at least one of:
- **Strong duplicate:** Title Jaccard similarity ≥ 0.6 between the proposed topic noun phrase and the existing Epic title, OR exact match on an `Epic: *` label slug.
- **Possible overlap:** Title Jaccard 0.4–0.6, OR the label slug shares ≥ 2 tokens with the proposed topic, OR the top 3 domain nouns from the user's utterance all appear in the existing Epic body.

#### 7.2 Exact Warning Prompt Wording

Strong duplicate:

> "Before creating a new Epic, I noticed **[Epic: slug-name](#N)** is already open and covers some of this ground ([overlapping domain nouns]). Is your request distinct from that scope, or should we work within that existing Epic?"

Possible overlap:

> "There might be some overlap with **[Epic: slug-name](#N)** — want me to check if this fits there or if it's distinct enough for its own Epic?"

#### 7.3 Three Resolution Paths

| User Response | Agent Action | Transition |
|---|---|---|
| "Use the existing one" / "work within that" / "yes, that's it" | Link remaining session to existing Epic (use its issue number going forward) | → PLANNING_MODE using existing Epic body |
| "No, mine is different" / "create new anyway" / "separate thing" | Proceed with new Epic creation | → AWAITING_CONFIRMATION (Scenario A prompt) |
| "Cancel" / "never mind" / "forget it" | Post cancellation message, return to idle | → ABANDONED |

For the "use existing" path, the agent re-reads the existing Epic body to reconstruct what has already been answered (§8) before continuing the Q&A.

---

### 8. Session Resumption

#### 8.1 Re-Entry Trigger

A session is resumable when:
- The user says "let's continue the [name] Epic" / "where were we on #[N]" / "pick up from the [X] planning", OR
- The agent detects a HIGH-confidence signal for a topic that matches an open Epic issue with a `PLATE_SESSION_STATE` block in its body.

#### 8.2 State Reconstruction

The agent reads the `PLATE_SESSION_STATE` block from the Epic issue body:

```
<!-- PLATE_SESSION_STATE -->
phase: building_children
last_step: out_of_scope
child_issues: [101, 102]
<!-- /PLATE_SESSION_STATE -->
```

From this block, the agent reconstructs:
- **Current phase** (`planning_mode` or `building_children`)
- **Last completed Q&A step** (maps to a turn number in the arc)
- **Existing child issues** (already created stubs, to avoid re-creation)
- **Completed sections** (by reading which body sections are non-empty and non-placeholder)

#### 8.3 Re-Entry Prompt to User

> "Last time we got to [last_step in human-readable form] on **[Epic title] (#N)**. The open questions were: [list of unanswered steps]. Want to continue from there?"

Example:

> "Last time we got to the out-of-scope guard on **Notification System (#47)**. We still need to flag dependencies and propose child issues. Want to continue from there?"

The agent does not repeat already-answered questions. It starts from the next unanswered step in the arc.

---

### 9. Graceful Degradation

#### 9.1 User Stops Mid-Session

If the agent sends a Q&A question and the user does not respond in that turn (or responds off-topic):

1. The agent does not wait indefinitely. After one unanswered follow-up, it proceeds with scaffolded defaults for all remaining open steps.
2. All unanswered items are written as `[unanswered — assumed: X]` in the Epic body.
3. The agent edits the Epic body with the scaffolded defaults.
4. The agent posts a comment on the Epic issue:
   > "⏸️ Planning session paused. I've saved what we covered so far and filled in defaults for the rest. Resume any time by continuing our conversation or mentioning #[N]."
5. The `PLATE_SESSION_STATE` block is updated to `phase: paused`.

#### 9.2 User Gives Consistently Vague Answers

Defined as two or more consecutive answers that do not produce a testable statement.

1. The agent names the pattern, not the user: "I'm having trouble finding a specific target — let me try a different angle."
2. The agent switches from open questions to bounded-choice questions (2–3 concrete options).
3. If bounded-choice questions also produce vague answers, the agent scaffolds the most conservative default and flags the criterion as `[low-confidence — needs-review]`.
4. After two escalation attempts on the same dimension, the agent stops asking and proceeds with what it has.
5. Any child issues created in this context receive the `need:refinement` label (already applied at creation — no change needed).
6. If the entire artifact is low-confidence, the agent notes this in the Epic body:
   > "_This plan is based mostly on defaults and may need significant revision once requirements are clearer._"

#### 9.3 User Explicitly Cancels

If the user says "stop", "cancel", "abandon", "forget this", or "I don't want to do this" at any point:

1. The agent replies:
   > "Understood — canceling that. Any issues I've already created are left open for you to edit or close manually. What would you like to do instead?"
2. The agent posts a comment on the Epic issue (if one was created):
   > "🚫 Planning session canceled by user. Issues remain open for manual editing."
3. The `PLATE_SESSION_STATE` block is updated to `phase: abandoned`.
4. The agent transitions to IDLE and does **not** create any further child issues.
5. No issues are deleted or closed automatically. The user retains full control over existing issues.

---

## Open Questions

1. **Label slug format:** Should `Epic: [slug]` use the Epic issue title as-is or a normalized kebab-case slug? The label creation step is not covered in this design and needs a decision before implementation. → Open `need:decision` issue.
2. **Duplicate check scope:** Should the duplicate check run only against open Epics in the same repo, or across all repos in the org? Current design assumes single-repo scope.
3. **Fast-path threshold:** The 6-word threshold for short replies is heuristic. It should be validated against real session transcripts once the feature is live.
4. **Session state HTML comment:** The `PLATE_SESSION_STATE` HTML comment block is machine-readable but visible to users who read the raw Markdown. Consider whether a dedicated JSON metadata field (if GitHub ever exposes one) would be cleaner.
5. **Child issue order:** Research → Design → Feature is the default order. Some Epics may not need all three types. Deciding which types to propose requires a heuristic that is not yet defined.

## Acceptance Evidence

This design is correctly implemented when:

1. A test conversation reaching HIGH confidence produces exactly one opt-in confirmation prompt before any issue is created.
2. A test conversation where the user declines produces zero GitHub issues.
3. A test conversation that completes turns 1–6 produces an Epic issue body with all four sections (`## Acceptance Criteria`, `## Scope`, `## Out of Scope`, `## Dependencies`) populated.
4. After each Q&A turn, running `gh issue view [N]` shows the updated section and an updated `PLATE_SESSION_STATE` block.
5. A resumed session (starting from a `PLATE_SESSION_STATE` block with `last_step: out_of_scope`) skips turns 1–5 and resumes at turn 6.
6. A canceled session leaves the Epic issue open with a cancellation comment and `phase: abandoned` in the session state block.
7. A conversation about an existing Epic (containing `#N` in the utterance) does not trigger the confirmation prompt (suppression rule verified).
8. A duplicate topic (Jaccard ≥ 0.4) produces the Scenario B warning prompt, not the Scenario A prompt.
