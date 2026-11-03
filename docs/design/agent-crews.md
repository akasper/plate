# Agent crews — Design Spec

- **Epic:** [#1327](https://github.com/akasper/plate/issues/1327) (Agent crews milestone)
- **Parent doc for:** task spec ([#1333](https://github.com/akasper/plate/issues/1333)), resource router ([#1337](https://github.com/akasper/plate/issues/1337)), baseline roles ([#1336](https://github.com/akasper/plate/issues/1336) / [#1349](https://github.com/akasper/plate/pull/1349)), reviewer gate ([#1334](https://github.com/akasper/plate/issues/1334)), tiered CI ([#1332](https://github.com/akasper/plate/issues/1332)), spend ledger ([#1352](https://github.com/akasper/plate/issues/1352) / [#1358](https://github.com/akasper/plate/pull/1358)), Jev shadow scoring ([#1356](https://github.com/akasper/plate/issues/1356)), pilot ([#1338](https://github.com/akasper/plate/issues/1338), [#1353](https://github.com/akasper/plate/issues/1353)), deferred crew app ([#1357](https://github.com/akasper/plate/issues/1357))
- **Status:** Design (implementation tracked in child issues; no pilot savings claimed yet)

## Problem and thesis

PLATE already supports a single-agent development loop well, but product work spans validation, design, GTM, marketing, operations, support, finance, and other lifecycle stages. Teams of narrow role agents (and humans) need predictable **task contracts**, **tier-appropriate models**, and **runtime routing** without duplicating policy in every host.

**Thesis:** A crew model—one coordinator planning work from a machine-readable task spec, one implementer, and a reviewer on a different model with clean context—should **lower all-in cost per accepted outcome** compared with a single generalist agent on the same tasks, without making escaped defects worse. That hypothesis is **not validated yet**; the paired pilot on plate and DentalCoach ([#1338](https://github.com/akasper/plate/issues/1338), protocol stub [#1353](https://github.com/akasper/plate/issues/1353)) exists to test it. No savings or win is claimed in this document.

Scope is the **whole product lifecycle**, not development alone ([#1327](https://github.com/akasper/plate/issues/1327#issuecomment-6590632904), [#1353](https://github.com/akasper/plate/issues/1353#issuecomment-6590798351)): some tasks have a clear flowchart route; others are ambiguous and need explicit `route` / approval fields in the task spec.

## Andrew's six decisions (2026-11-02)

Recorded on [#1327](https://github.com/akasper/plate/issues/1327#issuecomment-6590632904) and relayed by the Development Coordinator:

| # | Decision |
|---|---|
| 1 | **Win metric:** all-in cost per **accepted** outcome (coordinator and reviewer included); escaped defects no worse than baseline; **30%** improvement threshold fixed **before** the pilot starts. |
| 2 | **Pilot:** the same ~**20** tasks run both ways (crew vs current flow) on **plate** and **DentalCoach**, capped at **12 points** of the weekly allowance; results are directional at this sample size ([#1353](https://github.com/akasper/plate/issues/1353)). |
| 3 | **Coordination:** one **writer** plus a **different-model reviewer** with clean context; a manager may **split work only** when the task spec declares **separate file paths**; **no chains** of narrow role agents on code. |
| 4 | **Levels and tiers:** fixed table (below); `risk:critical` needs a human approver; cheaper model first for junior **docs** and **tests** where CI checks the result; **Jev scores alongside** the fixed table without routing ([#1347](https://github.com/akasper/plate/issues/1347), [#1356](https://github.com/akasper/plate/issues/1356)). |
| 5 | **Crew application:** **not now**—router stays a **plate_core** library and CLI; after a pilot win, a **Cloudflare Agents + Workflows** coordinator in its **own repo** with its **own Grok Bot** ([#1357](https://github.com/akasper/plate/issues/1357)). |
| 6 | **This epic:** commit this parent design doc, keep child issues as the implementation record, close **#1327** when merged. |

**Label decision** (same thread, replaces the proposed `role:*` / `level:*` / `route:*` labels in the original #1327 body): add only optional `tier:T0`–`tier:T3`. Role is inferred from issue type and labels (for example `area:*`); **level** and **route** live in the task spec or PR body, not as GitHub labels.

## Crew model

```text
Human or PM host (coordinator)
        │
        ├─► Planner pass: write or refine .agentic/tasks/<id>.yml (task spec)
        │
        ├─► Writer: one implementer run (role + level + route from spec)
        │
        └─► Reviewer: separate run, different model/provider, clean context
                    (see reviewer-differs rule; human merge approval unchanged)
```

- **One planner** produces or updates the **task spec** before implementation spend (schema and validator: [agent-crews-task-spec.md](agent-crews-task-spec.md)).
- **One writer** executes the spec; avoid multi-hop “designer → coder → tester” chains of narrow catalog personas on the **same code change**.
- **Splitting:** a manager may assign parallel writers **only** when the task spec lists **disjoint output file paths** (or equivalent scoped artifacts)—not ad hoc file-grab delegation.
- **Humans** may fill any catalog role; crew policy does not remove existing human gates.

Future orchestration (deferred): [§ Deferred crew application](#deferred-crew-application).

## Roles and baseline catalog

Narrow lifecycle roles (PM vs team lead, designer variants, GTM, marketing, LiveOps, ML, customer success, and related entries) live in **`src/plate_core/data/baseline_catalog.yml`**, with skills and **`default_tool_profiles`** per role, schema validation, and label-based inference via `infer_role_from_issue()` ([#1336](https://github.com/akasper/plate/issues/1336), merged [#1349](https://github.com/akasper/plate/pull/1349)).

- Discover ids: `gh plate agents list` (see release fragment `narrow-baseline-catalog-roles-1336.json`).
- Task specs reference a catalog **`role`** id; GitHub issues do **not** use `role:*` labels.
- The hand-authored **`plate`** coordinator persona is unchanged.

## Task spec

Machine-readable contracts: `.agentic/tasks/<id>.yml`, JSON Schema in plate_core, validator CLI—full field reference in [agent-crews-task-spec.md](agent-crews-task-spec.md) ([#1333](https://github.com/akasper/plate/issues/1333)).

Task specs carry **`level`**, **`route`**, **`model_policy`**, **`tools`**, **`acceptance`**, **`approval`**, and **`budget`**; procedures under `.agentic/procedures/` chain specs for multi-step workflows.

## Level and tier mapping

| Level | Typical tier start | Notes |
|---|---|---|
| **junior** | **T1** (economical hosted; e.g. DeepSeek via OpenRouter per #1327) | Prefer cheaper models for **docs** and **tests** when CI validates output |
| **senior** | **T2** (default crew band; e.g. composer-2.5 low effort) | Default implementation band |
| **staff** | **T3** or a **human** | `model_policy.t3_requires_approval: human` + approval gate in spec |

**GitHub `tier:*` labels** (optional, at most one, non-exclusive with type and `risk:*`):

| Label | Meaning (#1327) |
|---|---|
| `tier:T0` | Local / low-latency |
| `tier:T1` | DeepSeek via OpenRouter |
| `tier:T2` | composer-2.5 at low effort |
| `tier:T3` | Higher effort or Claude; **human approves per task** before use |

**Escalation:** at most **one** tier step per run (`model_policy.escalation`), then stop and report—never silent downgrade below allowed tiers.

**Risk:** issues or PRs with **`risk:critical`** require a **human approver** on the path to merge (unchanged PLATE authority model).

Labels **`level:*`**, **`route:*`**, and **`role:*`** are **not** used; keep level and route in the task spec.

## Resource router (interface only)

Runtime assignment (model, local runtime, or human) reads PLATE files only—registry record, routing inputs/outputs, optional Consumption Tracker and Lull snapshots, and the reviewer-differs constraint at route time. Specification: [agent-crews-resource-router.md](agent-crews-resource-router.md) ([#1337](https://github.com/akasper/plate/issues/1337)). **Implementation is deferred** to follow-up features; until then hosts use the fixed level/tier table above.

## Jev scoring (shadow mode)

[#1347](https://github.com/akasper/plate/issues/1347) asks whether Jev can route junior/senior/staff cheaply enough; **Andrew's decision (#4)** keeps routing on the **fixed table** for now.

[#1356](https://github.com/akasper/plate/issues/1356): Jev **scores tasks alongside** the table and **records** scores; it **does not route**. Score records should capture the full routing factor set (model, tier, hardware via Lull, route clarity, lifecycle task type) during early measurement so outcomes can be compared later ([#1356](https://github.com/akasper/plate/issues/1356#issuecomment-6590798351)). **Do not use Jev to choose tier or resource until shadow mode has at least 60 labeled runs** to evaluate routing quality ([#1347](https://github.com/akasper/plate/issues/1347), [#1356](https://github.com/akasper/plate/issues/1356)).

Ledger fields that support this observation (when recorded): `tier`, `hardware`, `route_clarity`, `lifecycle_task_type` on `spend_interval` rows ([#1352](https://github.com/akasper/plate/issues/1352)).

## Reviewer differs from author

[#1327](https://github.com/akasper/plate/issues/1327) requires a reviewer that is **never the same model** and ideally a **different provider**. Implementation ([#1334](https://github.com/akasper/plate/issues/1334)):

- PR template **Agent review models** table (author vs reviewer); **`copilot`** is allowed for GitHub Copilot review.
- `plate_core.pr_reviewer_model_gate` / **pr-gates**: **warn-only** in the first release (missing table, same model id, or shared provider); **`--enforce`** can block same-model later.
- **Human merge approval** is unchanged.

Router-level fingerprint rules: [agent-crews-resource-router.md](agent-crews-resource-router.md#router-inputs).

## Measurement and spend ledger

**Win metric (pilot):** all-in **`cost_per_accepted_outcome_usd`** from recorded spend, with coordinator and reviewer runs attributed to the same outcome where possible; compare crew vs baseline with escaped defects no worse ([#1353](https://github.com/akasper/plate/issues/1353)).

**Ledger:** `record_type=spend_interval` under `.agentic/ledger/` ([#1352](https://github.com/akasper/plate/issues/1352), [#1358](https://github.com/akasper/plate/pull/1358)). Record only measured fields—never invent tokens or cost.

| Field group | Examples (optional on each interval) |
|---|---|
| Identity | `run_id`, `cloud_agent_id`, `parent_run_id`, `session` |
| Routing | `model`, `tier`, `effort`, `hardware`, `route_clarity`, `lifecycle_task_type` |
| Tokens | `input_tokens`, `output_tokens`, `cached_read_tokens`, `cache_write_tokens`, `tool_output_tokens`, `turns` |
| Handoff | `handoff_packet_size`, `handoff_packet_unit`, `rediscovery_count` |
| Outcome | `outcome_accepted`, `cost_usd`, `related_issue`, `related_pr` |

Reporting: `gh plate costs --spend-report`, `gh plate costs --run-cost --run-id …`, MCP `plate_costs` / `plate_ledger_record_spend` (see [docs/mcp.md](../mcp.md)). Unattributed intervals are listed separately—never split evenly.

Baseline and crew arms of the pilot should use the same measurement hooks ([#1338](https://github.com/akasper/plate/issues/1338)).

## Pilot

Protocol detail: **`docs/design/agent-crews-pilot-protocol.md`** when merged; until then [#1353](https://github.com/akasper/plate/issues/1353) (paired crew vs single-agent runs, plate + DentalCoach).

Fixed before start ([#1353](https://github.com/akasper/plate/issues/1353), decision #1–#2): **30%** cost-per-accepted-outcome threshold, ~**20** shared tasks, **12** weekly allowance points cap, honest reporting including negative results.

Depends on spend ledger landing for attribution ([#1352](https://github.com/akasper/plate/issues/1352)).

## Supporting slices (linked, not duplicated)

| Topic | Doc / issue |
|---|---|
| Tiered, path-based CI (cheaper PR path) | [#1332](https://github.com/akasper/plate/issues/1332), `docs/migration/tiered-ci-policy.md` |
| MCP tool profiles (spec tool allow-lists) | [#1331](https://github.com/akasper/plate/issues/1331) |
| Optional `tier:*` in label-check | [#1328](https://github.com/akasper/plate/issues/1328) |
| Wake reduction | [#1335](https://github.com/akasper/plate/issues/1335), [Reducing agent wakes](../wiki/Reducing-Agent-Wakes.md) |

## Deferred crew application

**Not in this repository now.** Router and registry remain **plate_core** library + CLI surfaces.

After a **pilot win**, design a **Cloudflare Agents + Workflows** crew coordinator in a **separate repository** with its **own Grok Bot** ([#1357](https://github.com/akasper/plate/issues/1357)), blocked on pilot results ([#1338](https://github.com/akasper/plate/issues/1338)).

## Human-approved (unchanged)

From [#1327](https://github.com/akasper/plate/issues/1327): merges and releases; gate or merge-policy changes; scope and public claims; anything external; money movement; production deploys; branch protection; installing runners; **T3 use per task**; **`risk:critical`** approval paths.

## Related artifacts

- [agent-crews-task-spec.md](agent-crews-task-spec.md)
- [agent-crews-resource-router.md](agent-crews-resource-router.md)
- [cost-control narrow delegation packets](cost-control-narrow-delegation-packets.md) (#395)
- Epic milestone: **Agent crews**
