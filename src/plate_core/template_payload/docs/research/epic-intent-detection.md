# Research: Epic-Intent Detection and False-Positive Handling

- **Issue:** #81
- **Researched by:** @copilot
- **Date:** 2026-05-26
- **Status:** Complete — awaiting human decision

## Research Question

How should the Copilot agent reliably detect when a user is expressing epic-planning intent versus casual conversation, without generating false positives that interrupt unrelated discussions?

## Sources

- Issue #81 (parent research question and decision criteria)
- Issue #73 (Epic planning session that surfaced the need for soft-detection + confirm)
- `AGENTS.md` §Required Work Loop > Research and §Autopilot Doctrine
- `.agentic/skills.yml` (current agent skill surface, reviewed for intent-routing gaps)
- Existing research artifacts: `automatic-epic-creation.md`, `information-goals.md`
- Prior art: LLM intent classification literature (slot-filling, zero-shot NLI for dialogue acts)

## Findings

### 1. Signal Taxonomy

Epic-planning intent signals fall into three tiers. Tier 1 signals are near-certain; Tier 2 are probable; Tier 3 require corroborating context.

#### Tier 1 — Direct, High-Confidence Signals

These phrasings contain explicit creation or planning verbs paired with a product or capability noun.

| Pattern | Example |
|---|---|
| "I want to build X" | "I want to build a notification system" |
| "let's plan out Y" | "let's plan out the auth overhaul" |
| "we need to think through Z" | "we need to think through the migration strategy" |
| "let's create an epic for X" | "let's create an epic for the dashboard work" |
| "I'd like to track X as an epic" | "I'd like to track the reporting work as an epic" |
| "can we scope out X" | "can we scope out the mobile release" |
| "let's design the X system" | "let's design the billing system end-to-end" |
| "what does it take to build X" (with stated goal) | "what does it take to build a real-time chat feature, and can we plan it?" |

Key markers: imperative or first-person future-planning verbs (`build`, `plan`, `design`, `scope`, `track`, `create`, `tackle`, `start`), combined with a product-domain noun that is not already a known issue title or label.

#### Tier 2 — Indirect, Moderate-Confidence Signals

These phrasings are exploratory rather than declarative but still indicate forward-looking intent toward a new capability area.

| Pattern | Example |
|---|---|
| "how would X even work?" (with novel scope) | "how would a live-collaboration feature even work in this app?" |
| "maybe we should tackle Y" | "maybe we should tackle the permissions model next" |
| "what if we added X" | "what if we added a plugin system?" |
| "I keep running into X, we should fix it holistically" | "I keep hitting auth errors, we should fix the whole auth flow" |
| "we've been putting off X long enough" | "we've been putting off the admin panel long enough" |
| "at some point we need X" | "at some point we need a proper onboarding flow" |

Key markers: hedged modality (`maybe`, `might`, `should`, `could`, `what if`), temporal urgency cues (`keep`, `long enough`, `at some point`), or rhetorical questions about feasibility that imply ownership.

#### Tier 3 — Weak / Contextual Signals

These are only meaningful in combination with other signals, not on their own.

- Mentions of a product area without a verb of creation or planning.
- "That's a big project" or similar scale acknowledgments.
- Asking about architecture or design patterns without any stated intent to act.

#### False Positives — Patterns That Must NOT Trigger Detection

The agent must explicitly suppress detection when any of the following conditions hold:

| False-Positive Pattern | Why It Fires Spuriously | Suppression Rule |
|---|---|---|
| "looking at Epic #42 / the auth epic" | Reference to an existing epic by number or label | If the utterance contains an issue number (`#N`), a known `Epic: *` label name, or the phrase "epic #" → suppress |
| "in the last sprint we built X" | Retrospective analysis, past tense | If primary verb cluster is past tense (`built`, `shipped`, `fixed`, `released`, `deployed`) → suppress |
| "theoretically, how would X work?" | Hypothetical / academic discussion | If `theoretically`, `hypothetically`, `in theory`, `just curious`, `for my understanding`, `not planning to` → suppress |
| "can you explain how X works?" | Information request, not planning intent | Pure interrogative without first-person planning subject → suppress |
| "I read that Y is hard to build" | External reference, no first-person intent | Subject is third-party ("they", "teams", "companies", "I read") → suppress |
| Answering a question about an existing issue | Resolving confusion, not proposing new work | If conversation is already inside an active issue thread → suppress |
| "add a task to epic X for Y" | Adding to existing epic, not creating | If `add`, `append`, `put under`, `belongs to` precedes known epic reference → suppress |

---

### 2. Confidence Scoring Heuristic

A lightweight decision rule for in-chat use. Score each signal count independently, then sum.

#### Scoring Inputs

| Factor | Condition | Points |
|---|---|---|
| **Explicit creation verb** | Contains `build`, `create`, `plan`, `design`, `scope`, `track` as primary verb | +3 |
| **Implicit planning verb** | Contains `tackle`, `fix holistically`, `address`, `start`, `kick off` | +2 |
| **Future / intention marker** | Contains `want to`, `need to`, `should`, `going to`, `let's` | +1 |
| **Novel domain noun** | Subject noun is NOT a known issue title, open epic label, or existing PR title | +2 |
| **Known domain noun** | Subject noun IS a known issue, epic label, or existing PR | −3 |
| **First-person subject** | "I", "we", "us" as grammatical subject | +1 |
| **Scale or complexity cue** | "end-to-end", "holistically", "whole", "overhaul", "system", "platform" | +1 |
| **Past-tense suppression** | Primary verb cluster is past tense | −5 |
| **Hypothetical suppression** | "theoretically", "hypothetically", "just curious", "not planning" | −5 |
| **Issue-number reference** | `#N` or known epic label in utterance | −5 |
| **Question without subject** | Pure interrogative, no first-person planning subject | −3 |

#### Decision Thresholds

| Total Score | Confidence Level | Agent Behavior |
|---|---|---|
| ≥ 5 | **HIGH** | Surface confirmation prompt immediately |
| 3–4 | **MEDIUM** | Note signal internally; watch next 1–2 turns for reinforcement before prompting |
| ≤ 2 | **LOW** | Ignore; respond to the surface question normally |

**Important:** A score that starts HIGH but then accumulates a suppression trigger (e.g., user adds "just hypothetically") should be recalculated immediately and downgraded. Confidence is stateful within a conversation turn cluster, not sticky.

**Medium-signal accumulation:** If a conversation thread accumulates two MEDIUM signals within three consecutive turns about the same topic area, treat the combined signal as HIGH.

---

### 3. Confirmation Prompt Guidance

The agent must always ask before entering planning mode. The confirmation question should be:

- One sentence or two short sentences maximum.
- Opt-in phrasing (not opt-out).
- Specific about what "planning" means (creating an Epic issue).
- Easy to decline without awkwardness.

#### Scenario A — New Epic (High Confidence)

> "It sounds like you're thinking about building [X]. Want me to kick off an Epic for that — scope, success criteria, and child feature breakdown?"

Rationale: names the specific topic, uses "want me to" (opt-in), briefly describes what the agent will do.

#### Scenario B — Possible Duplicate Scope

> "I noticed there's already an open Epic for [similar topic] (#N). Are you thinking of something different, or would you like to work within that existing Epic?"

Rationale: surfaces the duplicate explicitly, gives the user two concrete options, does not assume the user is wrong.

#### Scenario C — User Is Just Browsing / Exploratory

> "Happy to think through [X] with you. If at any point you'd like to turn this into a tracked Epic, just say the word."

Rationale: validates the exploratory mode, removes pressure, plants an easy forward path.

#### Anti-patterns to Avoid

- ❌ "Should I create an Epic?" — too blunt; lacks specificity.
- ❌ "I'll go ahead and create an Epic for that." — no consent obtained.
- ❌ "Do you want to talk about this more?" — too vague; doesn't name the action.
- ❌ Multi-question prompts ("Do you want an Epic, or a spike, or just a chat?") — forces cognitive load; ask one thing.

---

### 4. Duplicate-Epic Detection

Before surfacing a confirmation prompt for a new Epic, the agent should run a lightweight duplicate check.

#### Detection Strategy

1. **Title similarity:** Tokenize the user's proposed topic noun phrase. Compare against the title of every open Epic issue using token overlap (Jaccard similarity ≥ 0.4 is a reasonable threshold for a short title). If `gh issue list --label Epic --state open` returns results, filter by title similarity.

2. **Label overlap:** Check whether any open Epic issue carries an `Epic: short-name` label whose slug shares two or more tokens with the proposed topic. Example: proposed topic "user authentication" → check for `Epic: auth`, `Epic: user-auth`, `Epic: authentication`.

3. **Body keyword match:** Retrieve the body of candidate Epic issues and check for presence of the top 3–5 domain nouns extracted from the user's utterance.

#### Similarity Tiers

| Similarity | Definition | Agent Response |
|---|---|---|
| **Strong duplicate** | Title Jaccard ≥ 0.6 OR exact label match | Show Scenario B confirmation prompt; do not proceed without explicit "something different" answer |
| **Possible overlap** | Title Jaccard 0.4–0.6 OR label slug shares ≥ 2 tokens | Show modified Scenario B with softer language: "There might be some overlap with Epic #N — want me to check if this fits there or if it's distinct enough for its own Epic?" |
| **No match** | Jaccard < 0.4, no label overlap | Proceed to Scenario A or C prompt as appropriate |

#### What to Say When a Duplicate Is Found

> "Before creating a new Epic, I noticed **[Epic: auth-overhaul](#42)** is already open and covers some of this ground (user authentication, session management). Is your request distinct from that scope, or should we work within that existing Epic?"

Always cite the specific issue number and name. Do not say "there might be something similar" without identifying it.

---

### 5. Ambiguity Handling

When intent is unclear (MEDIUM confidence, or conflicting signals), the agent should:

**Rule 1: Ask one targeted clarifying question — not multiple options.**

> "Are you thinking about this as something we'd want to track and build, or are you exploring it conceptually for now?"

This is a binary choice that resolves the main ambiguity (action intent vs. exploration) without overloading the user.

**Rule 2: Provide a brief anchor example when the topic is novel.**

If the proposed topic is highly abstract (e.g., "platform resilience"), offer a one-sentence framing to confirm mutual understanding:

> "When you say 'platform resilience', are you thinking about things like retry logic, fallback services, and SLA guarantees?"

**Rule 3: Wait for one more signal before prompting in MEDIUM cases.**

If confidence is MEDIUM, do not prompt immediately. Respond substantively to the user's question. If they continue the thread with more planning language in the next turn, upgrade to HIGH and prompt then.

**Rule 4: Do not prompt more than once per topic per session.**

If the user ignores or deflects the confirmation prompt, do not re-ask within the same conversation session. Note the topic as "user showed interest, declined to plan" and move on.

---

### 6. False-Positive Recovery

If the agent enters (or nearly enters) planning mode incorrectly, the graceful exit path is:

#### Agent-Initiated Recovery

If the user's response to a confirmation prompt makes it clear the detection was wrong (e.g., "No, I was just thinking out loud" / "That's already covered in #42" / "Not right now"):

> "Got it — no problem. I'll leave that as a discussion for now. Let me know if you want to revisit it."

Actions:
- Clear the MEDIUM/HIGH confidence state for this topic.
- Do not re-prompt for this topic in the session.
- Continue responding to whatever the user's actual question was.

#### User-Initiated Recovery

If the user explicitly says "stop planning mode" or "I didn't mean to create an Epic":

> "Understood — canceling that. Nothing was created. What would you like to do instead?"

Actions:
- If no issue was created yet: no cleanup needed.
- If an issue was drafted but not submitted: discard.
- If a stub issue was created (edge case, should not happen before confirmation): offer to close or delete it immediately with `gh issue close <N> --reason "not planned"`.

#### Psychological Design Principle

The agent should never make the user feel they triggered something unwanted or did something wrong. The exit phrase "no problem" or "understood" is load-bearing — it signals that the agent handles cancellation as a first-class action, not an error state.

---

## Recommendation

**Adopt the three-tier signal taxonomy and lightweight scoring heuristic** described in §1 and §2 as the primary detection mechanism.

Key implementation decisions:

1. **Threshold:** Set the HIGH trigger at ≥ 5 points and MEDIUM at 3–4, with a medium-accumulation rule (two MEDIUMs in three turns = HIGH). This keeps false-positive rate low while capturing genuine planning intent.

2. **Suppression is non-negotiable:** The past-tense, hypothetical, and issue-reference suppressors must be implemented before any prompt fires. These are the most common false-positive sources.

3. **Duplicate check before every HIGH-confidence prompt:** Always run the `gh issue list` + title-similarity check before presenting Scenario A. The cost is one API call; the benefit is avoiding duplicate Epic sprawl.

4. **One prompt, one question, one exit.** The confirmation prompt should never branch into multiple options. If duplicate detected → Scenario B. If new → Scenario A. If exploratory → Scenario C. Each branch has exactly one question and one graceful no-path.

5. **No operating rule changes to `AGENTS.md` or `.agentic/skills.yml` are required at this time.** The detection and confirmation logic should live in the agent's conversational layer (e.g., the Copilot Space context or a future `.agentic/skills.yml` `epic-intent-detector` skill). When that skill is implemented, a follow-up PR should update those files.

## Decision

**Open:** Awaiting human review.

Pending decisions for the human reviewer:

- **D1:** Accept recommended scoring thresholds (HIGH ≥ 5, MEDIUM 3–4) or adjust?
- **D2:** Should medium-accumulation rule (2 MEDIUMs in 3 turns = HIGH) be implemented, or is single-turn scoring sufficient?
- **D3:** Should the duplicate-detection Jaccard threshold (0.4) be tuned? Lower = more duplicate warnings; higher = fewer.
- **D4:** Should this heuristic be codified in `.agentic/skills.yml` immediately, or deferred until a skill implementation PR?

A follow-up Feature issue should be opened for the actual implementation of the detection skill once D4 is resolved.
