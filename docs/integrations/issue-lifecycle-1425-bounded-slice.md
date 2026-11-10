# Issue lifecycle — bounded integration slice (#1425)

This note documents **`plate_core.lifecycle_policy`** and **`gh plate process init`** as implemented
for [#1425](https://github.com/akasper/plate/issues/1425). It is an **integration supplement** only.

**Canonical design:** [PR #1432](https://github.com/akasper/plate/pull/1432) — `docs/design/issue-lifecycle.md`
(see also [issue-lifecycle.md](../design/issue-lifecycle.md) in-repo pointer).

## Scope

Pure / shadow policy: approver resolution, `lifecycle.gates` merge, taxonomy resolution from
`labels.issue_type_labels` / `labels.prefix_convention` + `lifecycle.taxonomy`, and approval-command
simulation. No live GitHub mutations, event log (#1443), or leases (#1445).

## Gate semantics

In `lifecycle.gates`, **`true` means human approval is required** for that gate key. **`false`**
means that gate does not impose that requirement in this bounded layer. Helpers:
`gate_requires_human_review`, `stricter_autonomy_cap`.

## Taxonomy (aligned with PR #1432)

`lifecycle.taxonomy` uses **`type_labels`**, **`prefixes`**, and **`tier_prefix`** as in the design doc.
Pure helpers resolve **`risk` / `need` prefixes** from `labels.prefix_convention` and **issue types**
from `labels.issue_type_labels` when references are used.

## `pending_write`

Canonical marker records (`transition_id`, `added`, `removed`) are enforced only via
`parse_pending_write_record` + `decide_approval_command(..., pending_write_record_json=...)`.
Substring “compliance” was removed as non-authoritative.

## CLI

`gh plate process init` **preserves an explicit `lifecycle.approvers` list** (including `[]` refuse-all).
An explicit **`approvers: null`** is **rejected on the init path** (no silent grant to token/owner).
Malformed approvers fail closed at runtime via `resolve_runtime_approvers`. It fills missing default
**`gates`** keys and merges **`lifecycle.taxonomy`** stubs when absent. Use **`--force-lifecycle`**
to replace approvers and gates.
