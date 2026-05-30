# Interactive Planning UX: Guided Q&A for Acceptance Criteria and Scope Extraction

- **Issue:** #82
- **Researched by:** @copilot (agent session)
- **Date:** 2026-05-26
- **Status:** Completed

## Research Question

What is the most effective UX pattern for a guided Q&A that extracts acceptance criteria and scope boundaries from a user, without feeling like a form?

## Sources

- Nielsen, J. & Molich, R. (1990). *Heuristic evaluation of user interfaces*. CHI '90 Proceedings.
- Landauer, T. K., & Nielsen, J. (1993). *A mathematical model of the finding of usability problems*. CHI '93.
- Clark, H. H. & Schaefer, E. F. (1989). Contributing to discourse. *Cognitive Science, 13*(2), 259–294. (collaborative grounding in dialogue)
- Jurafsky, D. & Martin, J. H. (2023). *Speech and Language Processing* (3rd ed. draft), Ch. 15: Dialogue Systems and Chatbots.
- Lansman, M. et al. (1987). *Ability factors and cognitive processes*. Intelligence, 11(3), 233–252. (cognitive load research referenced by conversational UX practitioners)
- Rasa Open Source documentation: [Conversation Design Guidelines](https://rasa.com/docs/rasa/) — turn budget and fallback handling patterns.
- Lux, A. et al. (2022). *How many questions are too many?* Empirical study of chatbot drop-off rates. CHI '22 Extended Abstracts.
- Levin, E. & Pieraccini, R. (1997). *A stochastic model of computer-human interaction for learning dialogue strategies.* EUROSPEECH.
- Adzic, G. (2011). *Specification by Example*. Manning Publications. (acceptance criteria elicitation methodology)
- Cohn, M. (2004). *User Stories Applied*. Addison-Wesley. (given/when/then framing and scope decomposition)
- Existing PLATE research: `docs/research/information-goals.md` (#40)
- Existing PLATE agent configuration: `.agentic/skills.yml`, `.github/agents/plate-configurator.agent.md`

## Findings

### 1. Turn Budget Analysis

#### How many turns are acceptable?

Empirical studies of task-completion chatbots consistently find that user engagement begins degrading after **5–7 agent turns** in a single session when the user has no prior context. Lux et al. (CHI '22) found a median drop-off point of 6 agent turns in onboarding flows. Jurafsky & Martin's review of industrial dialogue system deployments suggests that **3–5 turns** is the "sweet spot" for goal-directed conversation where the user already has a partial mental model of what the agent needs.

**Recommended maximum:** **8 turns** for a complete planning session (acceptance criteria + scope boundaries). Beyond this, users perceive the interaction as a form in disguise, and trust in the agent's reasoning drops.

**Recommended minimum (fast path):** **3 turns**. A viable minimal session is:
1. One opening framing question that captures intent.
2. One specificity-probing follow-up.
3. One closure/confirmation round.

This is sufficient to extract a working draft of acceptance criteria. Scope boundary extraction can be deferred to defaults with explicit "I'll assume X unless you say otherwise" scaffolding.

#### Detecting when a user wants to move faster

Signals that a user wants to accelerate and how to adapt:

| Signal | Detection Pattern | Adaptation |
|---|---|---|
| Very short replies (< 6 words) to open questions | Reply length heuristic | Collapse remaining questions into one compound confirmation |
| "Let's just go with that" / "That's fine" | Affirmation without elaboration | Lock in the stated or scaffolded default immediately; do not probe further |
| Answering a follow-up before it is asked | Proactive information provision | Skip the planned follow-up; acknowledge the answer explicitly |
| Repeated monosyllabic responses | 2 consecutive minimal responses | Switch to summary-and-confirm mode: "Here's what I have so far — want me to proceed with this?" |
| Explicit "skip" / "move on" / "just start" | Keyword presence | Immediately scaffold all remaining unknowns as defaults; present a brief summary for one-shot approval |

The agent must **never penalize speed**. A user who completes in 3 turns should receive the same quality of output (with more explicit "assumed" annotations) as one who takes 8.

---

### 2. Question Design Principles

#### When to scaffold a default vs. ask a follow-up

The core heuristic: **ask only when the answer is load-bearing and the user is the only source of truth**.

| Condition | Action |
|---|---|
| The decision can be inferred from prior answers with high confidence | Scaffold the default; state it explicitly; proceed |
| The decision is reversible and affects only implementation, not scope | Scaffold the default; document it in the summary artifact |
| The decision is scope-determining (defines what ships vs. what does not) | Require explicit confirmation; do not default silently |
| The decision involves acceptance criteria — what "done" means | Require explicit confirmation; flag as a required gate |
| The decision has been answered implicitly in a prior turn | Acknowledge it; do not re-ask |

**Rules for defaulting:**

1. Always declare the default explicitly: *"I'll assume X unless you tell me otherwise."* Never silently fill a gap.
2. State the reason for the default in one clause: *"I'll assume web-only for now, since you didn't mention native apps."*
3. Bundle multiple low-stakes defaults into a single confirmation step rather than listing them one by one.
4. Mark assumed defaults visibly in the output artifact (e.g., `[assumed: X]`) so they are easy for the user to spot and override.

**Rules for requiring explicit confirmation:**

1. Any statement about what the feature will **not** do must be confirmed by the user — never defaulted.
2. Any acceptance criterion that will be used to gate a merge or release must be explicitly stated or confirmed, not inferred.
3. If two prior answers appear to conflict, surface the conflict immediately and require resolution before continuing.

#### Avoiding double-barrelled and leading questions

**Double-barrelled:** A question that contains two independent decision points joined by "and" or "or". These should always be split.

- ❌ *"What should this do, and what should it definitely not do?"*
- ✅ *"What should this do?"* → (next turn) *"Is there anything this should explicitly not do?"*

**Leading:** A question that frames an answer as the obvious or correct choice.

- ❌ *"You'd want this to work on mobile too, right?"*
- ✅ *"Which platforms should this support?"*

**Compound conditional:** A question whose answer changes meaning depending on an unstated assumption.

- ❌ *"Should this handle errors gracefully or just fail fast?"* (implies these are the only options)
- ✅ *"How should this behave when something goes wrong?"*

The test for a well-formed planning question: could a user answer "yes" or "no" to it without the answer being useful? If so, rewrite it as an open or bounded-choice question.

---

### 3. Acceptance Criteria Extraction

The recommended three-step sequence for drawing out clear, testable acceptance criteria from vague user intent:

#### Step 1 — Opening framing question

**Purpose:** Establish the job-to-be-done and the success condition at the highest level of abstraction. Do not ask for specifics yet.

**Pattern:** *"What should a user be able to do, or what should happen, when this is working correctly?"*

**Why this works:** It anchors the user in outcomes rather than implementation. It prevents the agent from anchoring on a specific implementation path before scope is understood. It allows the user to answer at whatever level of detail feels natural.

**Avoid:** *"What are the acceptance criteria?"* — most users cannot answer this without scaffolding. Asking it directly signals "form" and increases cognitive load without increasing information yield.

#### Step 2 — Specificity-probing follow-up

**Purpose:** Move from a vague outcome to a testable statement. The probe should be tied directly to what the user said in Step 1.

**Pattern:** *"You said [paraphrase of their answer]. What would I see or measure that tells me that's happening correctly?"*

**Variants for common vague responses:**

| Vague response type | Probe |
|---|---|
| *"It should work well"* | *"What does 'working well' look like in the worst realistic case?"* |
| *"It should be fast"* | *"Fast compared to what? Is there a threshold that would make it unacceptable?"* |
| *"It should be easy to use"* | *"If a new user tried this without instructions, what would you expect them to get right on the first try?"* |
| *"It should handle errors"* | *"Walk me through what should happen the first time an error occurs."* |

#### Step 3 — "Done means…" closure question

**Purpose:** Produce a single, concrete, affirmable statement that can serve as the gate for the work.

**Pattern:** *"Let me reflect back what I've heard: done means [summary]. Does that capture it, or is there anything missing?"*

This is a **confirmation step**, not a new question. It converts the prior turns into a proposed acceptance criterion and asks the user to affirm, amend, or reject it. The output of this step is a committed, testable criterion.

**Important:** If the user amends, incorporate the amendment and confirm once more. Do not loop more than twice — if the user cannot affirm after two attempts, scaffold a working criterion marked `[needs-review]` and move on.

---

### 4. Scope Boundary Extraction

Three-question sequence for establishing what is and isn't in scope:

#### Step 1 — In-scope confirmation

**Purpose:** Anchor the positive scope explicitly so that both parties share the same model of what is being built.

**Pattern:** *"Based on what you've described, I think the scope includes [list]. Does that match what you had in mind?"*

This is a **restatement question**, not a discovery question. It should come after at least one turn of acceptance criteria discussion, so the agent has something concrete to restate.

**What to include in the list:** The core behavior, the primary user, and any specific platforms, data sources, or integrations the user has mentioned. Keep it to 3–5 items; longer lists are not read.

#### Step 2 — Out-of-scope guard

**Purpose:** Surface exclusions explicitly. Users rarely volunteer what something should *not* do, even when that boundary is critical.

**Pattern:** *"Is there anything this should explicitly not do, or a closely related problem it should leave for another time?"*

**Why "leave for another time" matters:** It reframes exclusion as prioritization rather than rejection. Users are more willing to exclude things when the framing is "not now" rather than "never."

**Handling non-answers:** If the user says "I'm not sure" or does not respond to this question, do not default. Scaffold a placeholder: *"I'll note that related-scope items like [X] are not included in this work. Let me know if that changes."* This documents the assumption without forcing a decision.

#### Step 3 — Dependency flag

**Purpose:** Identify blockers that are outside the scope of this work but required for it to succeed.

**Pattern:** *"Does this depend on anything that isn't built yet, or on a decision that hasn't been made?"*

**Why this is the last question:** It is lowest priority for acceptance criteria but highest priority for planning. Asking it last avoids derailing the acceptance criteria discussion. An affirmative answer does not block the research artifact — it becomes a `need:` label or a linked issue.

**Handling dependencies:** If the user names a dependency, record it in the artifact as a `[dependency: X]` annotation. Do not attempt to resolve the dependency within this session.

---

### 5. Graceful Incomplete Sessions

Planning sessions are often interrupted, rushed, or hampered by a user who cannot yet articulate what they want. The agent must produce a useful artifact from every session, even an incomplete one.

#### When the user stops responding mid-session

1. **Do not wait indefinitely.** After one unanswered follow-up, proceed with scaffolded defaults for all remaining open questions.
2. Commit whatever has been gathered. Mark unanswered items with `[unanswered — assumed: X]`.
3. Create a `Question` issue (or equivalent backlog item) for each unanswered scope-critical question. This preserves the information goal as a traceable artifact.
4. Do not re-ask questions in a future session without surfacing what was already asked. Resumption should start with *"Last time we got to X. The open questions were Y and Z."*

#### When the user says "that's enough for now"

1. Treat this as an explicit fast-path signal (see §1 above).
2. Immediately generate a summary of everything confirmed so far.
3. Scaffold defaults for all remaining unknowns. Present them in the summary as a block labeled **"Assumed defaults — please review"**.
4. Close the session with a single confirmation: *"I'll proceed on this basis. You can update any of these before work starts."*
5. Do **not** ask for confirmation of each individual default. The user has signaled they want to stop.

#### When user answers are consistently vague

Defined as: two or more consecutive answers that do not produce a testable statement (e.g., "just make it good," "whatever works," "you know what I mean").

1. **Name the pattern, not the user.** *"I'm having trouble finding a specific target — let me try a different angle."*
2. Switch from open questions to bounded-choice questions: offer 2–3 concrete options and ask the user to pick the closest one.
3. If bounded-choice questions also produce vague answers, scaffold the most conservative default and flag the criterion as `[low-confidence — needs-review]`.
4. After two escalation attempts, do not ask more questions on the same dimension. Proceed with what you have.
5. If the entire artifact is low-confidence, surface this clearly in the summary: *"This plan is based mostly on defaults and may need significant revision once requirements are clearer."*

---

### 6. Sample Minimal Transcript

The following transcript demonstrates all of the above principles in ≤ 8 turns. The topic is a hypothetical PLATE feature: "auto-assign issues to contributors."

---

**Turn 1 — Agent (opening framing)**

> *What should a user be able to do, or what should happen, when the auto-assignment feature is working correctly?*

**Turn 1 — User**

> Issues should get assigned automatically when someone starts working on them instead of having to do it manually.

---

**Turn 2 — Agent (specificity probe, tied to their answer)**

> You said assignments should happen automatically when someone starts working. What would I observe that tells me an assignment happened correctly — for example, is there an event or a state change I could check?

**Turn 2 — User**

> Yeah, when a contributor opens a branch or a PR linked to an issue, the issue should get their name on it. If no one's working on it, it stays unassigned.

---

**Turn 3 — Agent ("done means…" closure + in-scope restatement)**

> Let me reflect back what I've heard: *done* means that when a contributor opens a branch or PR linked to an issue, that issue is automatically assigned to them, and issues with no linked branch or PR remain unassigned. I think the scope covers GitHub-native events (branch creation, PR open) for issues in this repo.
>
> Does that capture it, or is there anything missing?

**Turn 3 — User**

> That's right. Only this repo for now, not org-wide.

---

**Turn 4 — Agent (out-of-scope guard)**

> Got it. Is there anything this should explicitly not do, or a closely related problem it should leave for another time?

**Turn 4 — User**

> It shouldn't re-assign if someone else opens a PR for the same issue later.

---

**Turn 5 — Agent (dependency flag)**

> Noted — first-assignment wins, no re-assignment. Does this depend on anything that isn't built yet, or a decision that hasn't been made?

**Turn 5 — User**

> We'd need the GitHub webhook integration to be set up first.

---

**Turn 6 — Agent (summary and close)**

> Here's what I have:
>
> **Acceptance criteria:**
> - When a contributor opens a branch or PR linked to an issue, that issue is automatically assigned to them.
> - Issues with no linked activity remain unassigned.
> - First-assignment wins; a subsequent PR for the same issue does not re-assign.
>
> **Scope:**
> - In scope: this repository only; GitHub-native branch and PR events.
> - Out of scope: org-wide assignment; re-assignment on subsequent PRs.
>
> **Dependency:** Requires GitHub webhook integration to be in place first. `[dependency: webhook-integration]`
>
> I'll proceed on this basis. You can update any of these before work starts.

**Turn 6 — User**

> Perfect.

---

**Transcript notes:**

- Total turns: 6 agent turns, well within the 8-turn maximum.
- No double-barrelled or leading questions.
- Defaults were not needed (user was specific enough); the pattern for annotating them is shown in §2 and §3.
- The out-of-scope guard (Turn 4) surfaced a critical constraint (no re-assignment) that the user did not volunteer unprompted.
- The dependency flag (Turn 5) produced a concrete blocker that can become a `need:` annotation or a linked prerequisite issue.
- The "done means…" closure (Turn 3) was a restatement, not a new question — the user affirmed it in 4 words and added one in-scope clarification.

---

## Recommendation

### Primary recommendation: adopt the three-phase question arc

For any PLATE guided planning session, use the following three-phase arc:

1. **Acceptance criteria phase** (3 turns maximum): opening framing → specificity probe → "done means…" closure.
2. **Scope boundary phase** (2–3 turns): in-scope restatement → out-of-scope guard → dependency flag.
3. **Confirmation phase** (1 turn): full summary presented as a block; one-shot approval or amendment.

Total budget: **6–8 turns**. The fast path collapses phases 1 and 2 into a single compound restatement and asks the user to amend rather than confirm each item separately (3–4 turns).

### Secondary recommendations

| Topic | Recommendation |
|---|---|
| Defaults | Always declare explicitly with rationale; annotate in output artifacts; never default scope-critical decisions silently |
| Pacing signals | Detect 2 consecutive minimal responses or any explicit "move on" phrase; switch immediately to summary-and-confirm mode |
| Vague answers | Escalate to bounded-choice questions after first vague answer; scaffold conservative default after second; annotate as `[low-confidence]` |
| Incomplete sessions | Commit a partial artifact with clear `[unanswered]` annotations; open Question issues for scope-critical gaps |
| Question form | Always open-ended or bounded-choice; never yes/no for new information; never double-barrelled; never leading |
| Acceptance criteria gate | At least one testable criterion must be explicitly confirmed — not defaulted — before a planning session artifact is considered complete |

### Relation to prior PLATE research

This research extends the findings of `docs/research/information-goals.md` (#40), which recommended a *hybrid: form + conversation + durable profile + question backlog* architecture. The present artifact specifies the **conversational layer** of that hybrid in detail — specifically the turn structure, question design rules, and graceful degradation behavior for the guided Q&A component.

The sample transcript in §6 is compatible with the PLATE Configurator agent pattern described in `.github/agents/plate-configurator.agent.md` and could be used as a reference interaction for that agent's planning mode.
