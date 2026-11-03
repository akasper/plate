# Agent crew resource registry and router — Design Spec

- **Issue:** #1337 (child of design #1327)
- **Designed by:** PLATE cloud agent session
- **Date:** 2026-11-02
- **Status:** Draft (interface only; implementation deferred)

## Problem

Task specs (`.agentic/tasks/*.yml`, see [agent-crews-task-spec.md](agent-crews-task-spec.md)) declare **what** a crew job needs: role, level, route, model tiers, token budget, and approval gates. A separate runtime component must decide **which concrete resource** executes the job—a local model, a hosted model endpoint, or a human—without duplicating PLATE policy in host-specific config.

This document specifies the **registry record shape**, **router inputs and outputs**, optional reads from **Consumption Tracker** and **Lull** telemetry (described generically), and the **reviewer-differs-from-author** constraint. No code, schema files, or GitHub label changes are in scope for #1337.

## Constraints

- PLATE repository files remain the source of truth; the router is a **reader** of task specs, baseline catalog, and optional `.agentic/` telemetry exports—not a second policy store.
- Tier vocabulary matches `plate_core.task_spec`: `T0`–`T3`, levels `junior` | `senior` | `staff`, routes `docs` | `tests` | `fix` | `feature` | `review`.
- At most **one** tier escalation step per task run (mirrors `model_policy.escalation`); after that the router stops and reports `blocked` with a human-visible reason.
- `T3` requires human approval per task spec (`t3_requires_approval: human` and a matching `approval` gate); the router must not assign `T3` until approval is recorded.
- Consumption and lull integrations are **optional adapters**; adopters without those feeds still route from registry + task spec + static availability.

## Level-to-tier policy table (#1355)

Andrew’s #1327 decisions (recorded in [agent-crews.md](agent-crews.md)) fix how **level** maps to model **tiers** before optional registry ranking. The same table is enforced in `plate_core.task_spec` (`LEVEL_TIER_POLICY`, `level_tier_policy_table()`) and documented in `task_spec.schema.json` under `$defs.level_to_tier_policy`.

| Level | Default tier | Allowed `model_policy.tiers` | Human assignable | Notes |
|---|---|---|---|---|
| **junior** | **T1** | T0, T1, T2 | no | **`start_tier` must not exceed T1.** For **`route: docs`** or **`route: tests`**, **`start_tier` must be the cheapest tier listed** in `model_policy.tiers` (cheaper model first when CI validates output). |
| **senior** | **T2** | T1, T2, T3 | no | Default implementation band; **`start_tier` must not exceed T2** (may start lower and use one escalation step). |
| **staff** | **T3** | T2, T3 | **yes** | Premium models or a **human** registry record (`kind: human`). When **T3** is used, `model_policy.t3_requires_approval: human` and a human **`approval`** gate are required (unchanged from task spec rules). |

**Risk:** When dispatch ties a run to a GitHub issue or PR carrying **`risk:critical`**, the task spec’s **`approval`** must be **`human-t3`** or stronger (`human-merge`, `human-release`, `human-external`). The router and validator treat this as a hard gate—no autonomous model path to merge.

**Labels:** Only optional **`tier:T0`–`tier:T3`** may appear on issues/PRs. Do **not** add `level:*`, `route:*`, or `role:*` labels; level and route stay in the task spec.

**Escalation:** At most one tier step per run (`model_policy.escalation`), consistent with the task spec validator; the router must not silently assign a tier outside the level’s allowed set.

## Resource registry record (interface)

Registry data is a set of records (future default location: `.agentic/resources/*.yml` or a single `.agentic/resources/registry.yml`—exact path is a follow-up issue). Each record describes one assignable endpoint.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `id` | string (kebab-case) | yes | Stable resource id referenced by router output |
| `kind` | `model` \| `local_runtime` \| `human` | yes | Resource class |
| `capabilities` | string[] | yes | Tags matched against task `route`, tool profiles, and catalog role skills (e.g. `review`, `docs`, `feature`, `code`) |
| `levels` | enum[] | yes | Subset of `junior`, `senior`, `staff` this resource can satisfy |
| `tiers` | enum[] | yes | Subset of `T0`–`T3` this resource implements (see tier mapping below) |
| `provider` | string | yes for `model` | Logical provider id (e.g. `local`, `openrouter`, `host-default`); used for reviewer-differs checks |
| `model_family` | string | no | Stable family id for models (not daily snapshot names); used with `provider` for identity |
| `identity_fingerprint` | string | yes for `model` | Opaque stable id combining provider + family (+ optional revision); two assignments with the same fingerprint count as the **same** model for review rules |
| `max_concurrent` | integer | no | Soft capacity (default 1 for models, higher for human pools) |
| `cost_hint` | object | no | `{ currency, per_1k_tokens_in?, per_1k_tokens_out?, flat_per_run? }` for ranking under budget |
| `availability` | enum | yes | `online` \| `degraded` \| `offline` \| `by_request` (humans) |
| `notes` | string | no | Operator-facing text; not used in routing logic |

**Tier mapping (policy reference, not registry-specific):** Design #1327 aligns tiers with capability bands—`T0` local/low-latency, `T1` economical hosted, `T2` default crew composer band, `T3` high-effort or premium models. Registry records list which tiers they implement; task specs list which tiers are **allowed** for that job via `model_policy.tiers` and `start_tier`.

Humans appear as registry records with `kind: human`, `availability: by_request`, and capabilities/levels reflecting staffed roles (product, design, release approval, etc.).

## Router inputs

The router accepts a **routing request** built by an orchestrator (PM, crew coordinator, or host) when starting or escalating a task run.

| Input | Source | Description |
|---|---|---|
| `task_spec_ref` | `.agentic/tasks/<id>.yml` | Resolved spec: `level`, `route`, `role`, `model_policy`, `budget`, `approval`, `tools` |
| `run_context` | Orchestrator | `task_run_id`, optional `issue_ref` / `pr_ref`, `requested_tier` (defaults to `model_policy.start_tier`) |
| `author_assignment` | Prior implementer run | Required when `route` is `review` or when selecting a reviewer: `{ resource_id, identity_fingerprint }` of the author |
| `approval_state` | Orchestrator / human gate | Whether `human-t3` (or stronger) approval is satisfied for this run |
| `registry_snapshot` | Registry loader | In-memory view of all records at route time |
| `consumption_snapshot` | Optional adapter | Normalized budget telemetry (see below) |
| `lull_snapshot` | Optional adapter | Normalized idle-capacity telemetry (see below) |
| `escalation_state` | Orchestrator | Whether the single allowed escalation step has already been consumed for this run |

Hard filters (must pass before ranking):

1. Resource `availability` is routable (`online` or `degraded` with policy flag; not `offline`).
2. Task `level` ∈ resource `levels`.
3. Requested tier ∈ task `model_policy.tiers` ∩ resource `tiers`.
4. Task `route` and role-required capabilities ⊆ resource `capabilities` (exact matching rules are implementation detail; conservative default: resource must advertise the route tag).
5. If requested tier is `T3`, `approval_state` must be satisfied.
6. **Reviewer-differs:** When selecting a resource for `route: review` (or a dedicated review pass), resource `identity_fingerprint` MUST differ from `author_assignment.identity_fingerprint`. Prefer a different `provider` when multiple candidates tie; never assign the same fingerprint as the author. Human reviewers always satisfy the rule. Hosted “second opinion” reviewers (e.g. optional Copilot review) are modeled as separate registry entries and must still differ by fingerprint from the author.

## Router outputs

| Output | Type | Description |
|---|---|---|
| `decision` | `assign` \| `escalate` \| `blocked` \| `defer` | Primary outcome |
| `resource_id` | string | Chosen registry id when `decision` is `assign` |
| `tier` | `T0`–`T3` | Tier used for this assignment |
| `level` | enum | Confirmed level (usually task level) |
| `estimated_cost_usd` | number | Optional; from `cost_hint` × budget caps |
| `reason_codes` | string[] | Machine-readable explanations (`budget_exceeded`, `no_capacity`, `reviewer_same_as_author`, `approval_pending`, `tier_not_allowed`, `lull_prefer_defer`, …) |
| `human_message` | string | Short operator-facing summary when `blocked` or `defer` |
| `escalation` | object | When `decision` is `escalate`: `{ from_tier, to_tier }` per task spec’s single step; orchestrator re-invokes with updated `requested_tier` |

Ranking (after hard filters): prefer (1) lowest tier that meets task minimum, (2) lower projected cost within `model_policy.max_cost_usd` and `budget.max_tokens_per_run`, (3) higher lull score when work is deferrable, (4) lower current consumption pressure on that tier/provider. Tie-break deterministically by `resource_id`.

When no resource passes filters and escalation is exhausted or disallowed, return `blocked`—do not silently downgrade below task `model_policy.tiers`.

## Reading Consumption Tracker data (generic)

**Consumption Tracker** is an optional external or adopter-operated service that aggregates **usage and budget burn** across providers and tiers. The router does not call billing APIs directly in this design; it reads a **normalized snapshot** produced by a PLATE-side adapter (scheduled job or MCP tool—implementation deferred).

Expected snapshot fields (versioned JSON document, refreshed on a cadence such as 1–5 minutes):

| Field | Meaning |
|---|---|
| `as_of` | ISO timestamp |
| `window` | e.g. `1h`, `24h`, `billing_period` |
| `budgets` | List of `{ scope_id, limit_usd, spent_usd, remaining_usd, tokens_in, tokens_out }` where `scope_id` may map to repo, crew, epic milestone, or `.plate` autonomy budget keys |
| `by_tier` | `{ T0..T3: { spent_usd, token_total, headroom_pct } }` |
| `by_provider` | Provider-level rollups for cross-provider review routing |
| `alerts` | Optional strings such as `approaching_limit`, `hard_stop` |

Router use:

- **Hard stop:** If `remaining_usd` for the relevant scope is below the task’s `model_policy.max_cost_usd` or autonomy budget policy, return `blocked` with `budget_exceeded`.
- **Soft ranking:** Deprioritize providers/tiers with low `headroom_pct` or active `hard_stop` alerts.
- **Escalation guard:** Before approving tier escalation, check that the target tier still has headroom in the consumption snapshot.

Adopters without Consumption Tracker omit the snapshot; routing uses task spec caps and registry `cost_hint` only.

## Reading Lull data (generic)

**Lull** is an optional signal source for **forecast idle capacity**—when queues are quiet enough to route deferrable or batch work to cheaper tiers without harming latency-sensitive jobs. Again the router reads a **normalized snapshot**, not live cluster metrics.

Expected snapshot fields:

| Field | Meaning |
|---|---|
| `as_of` | ISO timestamp |
| `resources` | List of `{ resource_id or provider, lull_score 0..1, queue_depth?, p95_latency_ms? }` |
| `global_lull` | Optional aggregate score for the crew or repo |
| `deferral_recommended` | Boolean when global pressure is high |

Router use:

- For non-urgent routes (`docs`, some `tests`), prefer resources with higher `lull_score` when tier and budget already satisfy the task.
- When `deferral_recommended` is true and the orchestrator marks the run as deferrable, return `defer` with `human_message` instead of consuming premium tier capacity.
- Do not use lull to bypass `review` reviewer-differs, approval gates, or hard budget stops.

Adopters without Lull omit the snapshot; ranking skips lull-weighting.

## Relationship to task spec and orchestration

```text
.agentic/tasks/*.yml          task level, route, model_policy, budget, approval
        │
        ▼
  Orchestrator ──► Router ──► registry record + tier assignment
        │                ▲
        │                │ optional snapshots
        ▼                │
  Consumption Tracker / Lull adapters (read-only, generic JSON)
```

- **Role** may still be inferred from GitHub issues via `infer_role_from_issue()` when dispatching; the router trusts the resolved spec’s `level`, `route`, and `model_policy`.
- **Workflow edges** (`next`) remain in procedures; the router only serves single-task assignment and escalation.
- **Review rule** applies both when `route: review` and when a procedure inserts an explicit review task after implementation: pass `author_assignment` from the implementer run.

## Alternatives rejected

| Alternative | Why rejected |
|---|---|
| Encode level/route/tier only as GitHub labels | #1327 / #1333 keep routing fields in task specs; labels would churn and duplicate spec truth |
| Router writes consumption or lull data | Violates read-only PLATE boundary; telemetry stays in external or `.agentic/` export files |
| Unlimited tier escalation | Conflicts with task spec validator and cost control; one step then stop |
| Same model reviews own output | Violates #1327 human-approved review rule; fingerprint check enforces differ |

## Open questions

- Canonical registry file layout and validation CLI (follow-up Feature).
- Whether `degraded` resources are eligible by default or require orchestrator opt-in.
- Standard mapping from MCP tool profiles to capability tags for matching.
- How approval timestamps are recorded in git (comment marker vs `.agentic/` run log).

## Acceptance evidence

- This design doc merged to `main` with `Closes #1337` in the PR body.
- Follow-up implementation issues wire: registry schema + validator, router library, Consumption/Lull adapter interfaces, and reviewer-differs enforcement in crew pilots.

## Related artifacts

- [agent-crews.md](agent-crews.md) — parent design (#1327 / #1354): crew model, levels, pilot, deferred application
- [agent-crews-task-spec.md](agent-crews-task-spec.md) — task spec fields the router consumes
- Design #1327 — epic requirements for crews, tiers, and review rule
- `src/plate_core/task_spec.py` — tier/level/route constants and validation rules
- [Reducing agent wakes](../wiki/Reducing-Agent-Wakes.md) — orchestration patterns that call the router sparingly
