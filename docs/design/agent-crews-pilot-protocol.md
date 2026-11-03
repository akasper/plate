# Agent crews pilot protocol (#1353 / design #1327)

This document defines how to run the **paired pilot** that compares a **single-agent (baseline) arm** with a **crew workflow arm** on the same tasks, on **plate** and **DentalCoach**. It implements the scope for [#1353](https://github.com/akasper/plate/issues/1353) and feeds the human-run pilot in [#1338](https://github.com/akasper/plate/issues/1338). Spend is recorded with the ledger from [#1352](https://github.com/akasper/plate/issues/1352) (see [docs/mcp.md](../mcp.md)).

**Related:** [agent-crews-task-spec.md](agent-crews-task-spec.md), [agent-crews-resource-router.md](agent-crews-resource-router.md).

---

## Decided before the pilot starts

These numbers and rules are **fixed in writing before any pilot run**. Do not change them mid-pilot to fit results.

| Item | Decision |
|---|---|
| **Win metric** | **All-in cost per accepted outcome**, including coordinator and reviewer spend, not just the implementer run. |
| **Quality guard** | **Escaped defects no worse** than the single-agent arm on the same task set (see [Defects and acceptance](#defects-and-acceptance)). |
| **Cost win threshold** | **30% lower** all-in cost per accepted outcome for the crew arm vs the single-agent arm on the paired set. |
| **Task count** | The **same ~20 tasks** on each repo, each run **both ways** (paired design). |
| **Spend cap** | **12 points** of the weekly allowance for the whole pilot (both repos, both arms, coordinators included). |
| **Sample size honesty** | Results at ~20 pairs are **directional only**. Detecting a true **30%** cost cut with typical variance needs on the order of **~30–76 paired tasks**, not ~20. Treat a win or loss at n≈20 as a signal for a larger study, not a final verdict. |

Andrew’s scope note (2026-11-02): measurement is **not dev-only**. The same protocol must cover **product lifecycle** work (validation, marketing, ops, support, finance, and similar) wherever outcomes are measurable. Some tasks have a **clear flowchart route**; others are **ambiguous**. Record routing inputs from the first run so future **Jev** routing can learn from labeled data (Jev stays in shadow until separately qualified; see [What this pilot does not cover](#what-this-pilot-does-not-cover)).

---

## DentalCoach and plate baselines

**DentalCoach has no merged-PR history** to build a trustworthy before/after baseline. On DentalCoach, the pilot **only** compares **paired runs** on the same tasks (single-agent arm vs crew arm). Do not claim a historical baseline there.

On **plate**, merged-PR history may inform **task selection** or informal expectations, but the **official comparison** for this pilot is still **paired arms on the same ~20 tasks**, not a time-series before/after. That keeps the two repos comparable and avoids mixing ceremony or repo maturity into the win metric.

---

## Arms

| Arm | Meaning |
|---|---|
| **Single-agent (baseline)** | Today’s default: one agent session (plus normal human merge/review gates), without crew task specs, narrow delegation packets, or a separate reviewer model with a clean context handoff. |
| **Crew workflow** | Task spec from `.agentic/tasks/` (see [agent-crews-task-spec.md](agent-crews-task-spec.md)), slim context, tier policy as declared in the spec, **one writer** plus **one reviewer on a different model** with clean context. A manager may split work **only** when the task spec declares **separate file paths**. **No chains of narrow role agents on code.** |

---

## Task selection

### Rules

1. **Human approval** of the final task list before the first run ([#1338](https://github.com/akasper/plate/issues/1338)).
2. **~20 tasks per repo**, matched in **intent and difficulty**, not necessarily identical issue numbers across repos.
3. Each task must have a **measurable accepted outcome** (mergeable PR, published doc, completed checklist artifact, approved copy, closed support playbook, etc.).
4. **Pairing ID:** assign a stable `pilot_pair_id` (e.g. `plate-01`, `dc-01`) shared by both arms on the same underlying task.
5. Prefer tasks that already exist as open or stub issues; do not invent fake customer data or fake financial numbers for the pilot.

### Mix (dev and non-dev)

Aim for a **deliberate mix** so lifecycle work is represented, not only coding:

| Category | Examples | Route clarity |
|---|---|---|
| **Development** | Bug fix, small feature, test-only change | Usually **clear** (`route` in task spec: `fix`, `feature`, `tests`) |
| **Documentation / design** | Design note, wiki page, research answer | Often **clear** (`docs`) |
| **Validation / QA** | Repro steps, regression checklist, release smoke | Clear or **ambiguous** |
| **Marketing / comms** | Release note fragment, landing copy, email draft | Often **ambiguous** |
| **Ops / support** | Runbook, triage decision tree, FAQ update | Mixed |
| **Finance / admin** | Pricing table update, invoice checklist (sanitized fixtures) | Often **ambiguous** |

For each task, record **`lifecycle_task_type`** on every ledger row (free-form string, e.g. `bug_fix`, `marketing_copy`, `support_runbook`). Record **`route_clarity`**: `clear` when the crew flowchart or PLATE issue type dictates the path; `ambiguous` when humans had to choose among multiple reasonable routes.

Tasks with **no objective acceptance signal** stay **out of scope** for the paired comparison (they may still be tracked informally).

---

## Pairing and order controls

Bias breaks the cost comparison. Apply these controls on **every** pair:

1. **Randomize arm order:** coin-flip (or sealed random list) whether **single-agent** or **crew** runs **first** for each `pilot_pair_id`. Log the order in run metadata.
2. **Same model tiers:** both arms use the **same approved tier table** for that task (`T0`–`T3` per [#1327](https://github.com/akasper/plate/issues/1327#issuecomment-6590632904)). Crew arm follows the task spec’s `model_policy`; single-agent arm uses the **same starting tier** and the same **one-step escalation then stop** rule.
3. **Same starting context:** same issue text, same repo snapshot (branch/commit or worktree), same allowed tools/MCP profile for that task class. Crew arm adds the task spec YAML and delegation packet; single-agent arm does **not** get extra policy pasted in beyond what that repo normally provides.
4. **Same human merge bar:** human approval rules unchanged. Escalation to human for `risk:critical` or `T3` approval applies to both arms equally.
5. **Cooldown:** where practical, separate the two arms by at least one sleep/wake boundary so transient host state does not favor the second run.

---

## Data recorded per run

Record **measured values only**. Never invent tokens, costs, or outcomes. Use **`gh plate ledger --record-spend`** (or `plate_ledger_record_spend`) per interval; attribute a full run with **`gh plate costs --run-cost --run-id <id>`** (or `--cloud-agent-id`). Summaries: **`gh plate costs --spend-report`**.

### Identity and linkage

| Field | Use |
|---|---|
| `run_id` | Primary key for one agent session (writer, reviewer, or coordinator each get their own id). |
| `parent_run_id` | Reviewer or coordinator row points at writer `run_id`. |
| `cloud_agent_id` | Host cloud agent id when applicable. |
| `related_issue` / `related_pr` | GitHub issue or PR for the task. |
| `metadata.pilot_pair_id` | Same id for both arms on one task (store in `metadata` JSON). |
| `metadata.pilot_arm` | `single_agent` or `crew`. |
| `metadata.arm_order` | `1` or `2` for run order within the pair. |
| `metadata.repo` | `plate` or `dentalcoach`. |

### Routing and lifecycle (#1352)

| Field | Use |
|---|---|
| `lifecycle_task_type` | Dev or non-dev category string for this task. |
| `model`, `tier`, `effort` | As executed (not as planned). |
| `hardware` | Lull or local resource id when used; empty otherwise. |
| `route_clarity` | `clear` or `ambiguous`. |

### Context and handoff quality

| Field | Use |
|---|---|
| `input_tokens`, `output_tokens`, `cached_read_tokens`, `cache_write_tokens` | As reported by the host. |
| `tool_output_tokens` | Tool-return volume for the interval. |
| `turns` | Agent turns in the interval. |
| `handoff_packet_size`, `handoff_packet_unit` | Delegation or reviewer packet size (bytes or tokens per unit recorded). |
| `rediscovery_count` | How often the agent re-found context the handoff packet should have carried (orchestrator counts per run). |

### Outcome and money

| Field | Use |
|---|---|
| `cost_usd` | Recorded spend for the interval when known. |
| `outcome_accepted` | Set only after human acceptance (see below). |

**All-in cost per accepted outcome** for an arm on a pair: sum **`cost_usd`** for all intervals with the same `run_id` tree (writer + reviewer + coordinator) where the task ultimately counts as accepted, using **`gh plate costs --run-cost`** on the root writer `run_id` plus linked child intervals, or the spend report’s **`cost_per_accepted_outcome_usd`** only when every interval and acceptance bit is recorded honestly.

---

## Defects and acceptance

### Accepted outcome

An outcome is **accepted** when a human with authority for that task type says it is done **without requiring rework**:

- **Code:** PR merged (or explicitly accepted without merge when merge is not applicable).
- **Docs / design / research:** merged Documentation PR or signed-off artifact path committed.
- **Non-dev:** explicit human sign-off recorded (issue comment, checklist, or approval marker) matching the task’s `acceptance.success_signal` in the task spec when crew arm is used.

Set **`outcome_accepted=true`** on the final writer interval (and optionally on reviewer interval) only after that signal. If the task is rejected or abandoned, set **`outcome_accepted=false`**.

### Escaped defect

An **escaped defect** is a **material problem** discovered **after** acceptance that **should reasonably have been caught** in review for that task type:

- Production or CI regression tied to the change.
- Factual error in customer-facing or financial copy after sign-off.
- Missing required PLATE gate (tests, labels, issue link) that review was supposed to catch.
- Rework requested on a “done” artifact for the same scope.

Track escaped defects in a simple pilot log (issue comment or spreadsheet): `pilot_pair_id`, arm, severity, found date, link. The **quality guard** fails if the crew arm’s escaped-defect rate is **worse** than the single-agent arm on the paired set (count or severity-weighted; pick one weighting before the pilot and stick to it).

### Reviewer-differs rule

On the **crew arm**, the **reviewer must not be the same model identity as the author** on the same task. Prefer a **different provider** when possible ([#1337](agent-crews-resource-router.md) / [#1334](https://github.com/akasper/plate/issues/1334)). Record author and reviewer models in the PR **Agent review models** table when the deliverable is a PR. Violating reviewer-differs invalidates that crew run for the cost comparison (re-run or discard).

Single-agent arm: normal repo review (human or Copilot) unchanged; still record models in the ledger **`model`** field for attribution.

---

## Stop rules

Stop the pilot immediately when **any** of these is true:

1. **75% of weekly allowance** consumed (pilot-wide or per Andrew’s pacing rule for the week—whichever limit is stricter in the pre-pilot brief).
2. **Any single paid charge** above the **agreed dollar limit** set before the pilot (exact amount recorded in the pilot brief, not here).
3. **12 points** of weekly allowance **spent** on pilot activity (both repos, all arms, coordinators and reviewers included).

When stopped, finish reporting for completed pairs only; do not start new pairs.

---

## Report format

Deliver one **honest** report (Documentation artifact or issue comment on [#1338](https://github.com/akasper/plate/issues/1338)) that includes:

1. **Pilot charter snapshot** — win metric, 30% threshold, stop rules, task list version, and allowance cap as fixed before start.
2. **Task table** — `pilot_pair_id`, repo, `lifecycle_task_type`, route clarity, arm order, accepted? (Y/N), escaped defects (Y/N + one-line note).
3. **Per-pair comparison** — all-in cost single-agent vs crew; token totals if recorded; do **not** fill in hypothetical savings.
4. **Aggregate** — mean/median all-in cost per accepted outcome by arm; escaped-defect counts; **`gh plate costs --spend-report`** summary or exported ledger slice.
5. **Directional conclusion** — whether evidence **suggests** meeting the 30% bar and quality guard at n≈20, with explicit **low power** disclaimer and the **~30–76 pairs** note for a definitive cost claim.
6. **Losses and anomalies** — tasks where crew lost on cost or quality, reviewer-differs violations, incomplete ledger rows, stop-rule trigger if any.

Do **not** publish fabricated percentages or invented token totals. Missing data stays missing.

---

## What this pilot does not cover

State plainly:

| Out of scope | Why |
|---|---|
| **Production Jev routing** | Router stays library/CLI; Jev remains in **shadow** until **60 labeled runs** exist elsewhere ([#1352](https://github.com/akasper/plate/issues/1352#issuecomment)). This pilot records routing fields for future use; it does not turn Jev on. |
| **Cloudflare Agents + Workflows coordinator** | Deferred until after a pilot **win** ([#1327](https://github.com/akasper/plate/issues/1327#issuecomment-6590632904)). |
| **Resource registry / router runtime** | Design only ([#1337](agent-crews-resource-router.md)); no registry enforcement in this pilot beyond task spec + manual discipline. |
| **Workflow-driven handoff vs code-graph benchmark ordering** | Workflow handoff is tested **before** code-graph benchmarks per Andrew’s ordering decision; code-graph comparison is a **later** benchmark, not this protocol. |
| **Dev-only narrow agent chains** | Chains of narrow role agents on **code** are **out of scope** and must not be used in the crew arm. |
| **Unmeasurable lifecycle work** | Tasks without an acceptance signal are excluded from paired cost comparison. |
| **DentalCoach historical baseline** | No before/after from merged PRs; paired arms only. |

---

## Human gates

- Approve the task list and pilot brief **before** run 1 ([#1338](https://github.com/akasper/plate/issues/1338)).
- Approve any **T3** or **`risk:critical`** path per task.
- Merge or sign off outcomes; only humans set **`outcome_accepted`**.
- Review the final report before treating the epic as ready for the next investment (coordinator repo, router runtime, etc.).

---

## Checklist before first run

- [ ] Win metric, 30% threshold, stop rules, and 12-point cap written and approved.
- [ ] ~20 tasks per repo listed with `lifecycle_task_type` and expected acceptance signal.
- [ ] Random arm order list generated.
- [ ] Ledger recording tested (`gh plate ledger --record-spend`, `gh plate costs --run-cost`) on a dry run.
- [ ] Reviewer-differs and tier rules understood by everyone running the crew arm.
- [ ] DentalCoach plan explicitly **paired comparison only** (no historical PR baseline).
