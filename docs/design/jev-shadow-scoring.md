# Jev shadow scoring (#1356)

**Status:** Design + minimal write path (shadow only). **Parent:** [agent-crews.md](agent-crews.md) ([#1327](https://github.com/akasper/plate/issues/1327)). **Related:** [#1347](https://github.com/akasper/plate/issues/1347), [#1135](https://github.com/akasper/plate/issues/1135), [#1129](https://github.com/akasper/plate/issues/1129), spend ledger [#1352](https://github.com/akasper/plate/issues/1352) / [#1358](https://github.com/akasper/plate/pull/1358).

## Purpose

Jev scores tasks **alongside** the fixed level→tier table and **records** its opinion. **Nothing in `plate_core` reads Jev fields to choose tier, model, hardware, or route.** Routing stays on the fixed table until product explicitly graduates Jev after enough labeled data.

**Win metric for eventual routing quality** (Andrew, [#1327 comment](https://github.com/akasper/plate/issues/1327#issuecomment-6590632904)): all-in **cost per accepted outcome**, including non-dev lifecycle work.

## Lifecycle scope (not dev-only)

Measurement must cover the **whole product lifecycle**: validation, marketing, ops, support, finance, and similar tasks—not only coding. Use a free-form `lifecycle_task_type` string on each row (examples: `feature_impl`, `marketing_copy`, `support_triage`, `ops_runbook`, `finance_reconcile`).

Some tasks have a **clear flowchart route**; others are **ambiguous**. Record both:

| Column group | Meaning |
|---|---|
| **Applied routing** (fixed table / host at run time) | `tier`, `model`, `effort`, `hardware`, `route_clarity` |
| **Jev shadow** (parallel opinion) | `jev_score`, `jev_suggested_tier`, `jev_model`, `jev_route_clarity` |

Compare Jev’s suggestion to applied routing and to **`outcome_accepted`** + **`cost_usd`** on the same or linked `run_id` / `cloud_agent_id` rows later—offline analysis only for now.

## Shadow mode gate

**Jev remains in shadow until at least 60 labeled runs** exist to evaluate routing quality ([#1347](https://github.com/akasper/plate/issues/1347), [#1356](https://github.com/akasper/plate/issues/1356)). Until then:

- Hosts may **write** Jev scores after (or with) spend attribution.
- Hosts must **not** branch execution on `jev_*` fields.
- Order of other experiments (per [#1327](https://github.com/akasper/plate/issues/1327#issuecomment-6590632904)): exercise workflow-driven handoffs before code-graph benchmarks; still record handoff / rediscovery fields on spend rows when measured.

## Storage: reuse `spend_interval`

Rows live under **`.agentic/ledger/`** with `record_type=spend_interval` (same store as [#1352](https://github.com/akasper/plate/issues/1352)). Optional Jev fields extend that record—no separate database.

| Field | Type | Notes |
|---|---|---|
| `jev_score` | number | Required for a Jev shadow write; opaque to PLATE (host-defined scale). |
| `jev_suggested_tier` | `T0`–`T3` | Jev’s tier suggestion; validated like `tier`. |
| `jev_model` | string | Model id Jev would assign. |
| `jev_route_clarity` | `clear` \| `ambiguous` | Jev’s route-clarity judgment. |

`metadata.jev_shadow_mode` is set to `true` on rows created via `record_jev_score` / `--record-jev-score` / `plate_ledger_record_jev`.

Spend rows may also carry token, handoff, and outcome fields from [#1352](https://github.com/akasper/plate/issues/1352) (`turns`, `tool_output_tokens`, `handoff_packet_size`, `rediscovery_count`, etc.) when measured—use the same row when possible, or link rows by `run_id`.

## Write paths (record only)

| Interface | Usage |
|---|---|
| CLI | `gh plate ledger --record-jev-score --run-id … --jev-score …` (+ optional Jev/applied routing fields) |
| CLI | `gh plate ledger --record-spend … --jev-score …` (single row with spend + Jev) |
| MCP | `plate_ledger_record_jev` (shadow score row) |
| MCP | `plate_ledger_record_spend` (optional `jev_*` on spend) |
| Library | `plate_core.ledger.record_jev_score`, `record_spend_interval` |

**List / filter:** `list_spend_intervals(..., jev_scored=True)` returns rows where `jev_score` is set (library API; no new CLI flag in this slice).

## Comparison workflow (later)

1. Record applied routing + spend on a run (`--record-spend` or automation).
2. Run Jev scorer offline; append shadow fields (`--record-jev-score` or same call with `jev_*`).
3. When outcome is known, set `outcome_accepted` and `cost_usd` on measured rows only.
4. Offline: join by `run_id`, compare `tier` vs `jev_suggested_tier`, `route_clarity` vs `jev_route_clarity`, and cost per accepted outcome—**no in-repo router changes in #1356**.

## Explicit non-goals (#1356)

- No resource router or tier picker reads `jev_*`.
- No automatic promotion from shadow to production routing.
- No invented scores, tokens, or outcomes—record measured values only.
