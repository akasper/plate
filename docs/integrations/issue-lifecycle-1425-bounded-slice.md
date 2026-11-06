# Issue lifecycle — bounded integration slice (#1425)

This note documents **`plate_core.lifecycle_policy`** and `gh plate process init` as implemented
for [#1425](https://github.com/akasper/plate/issues/1425). It is an **integration supplement** only.
Canonical lifecycle design (including gate semantics and full ceremony) belongs in the primary
design artifact for that effort (e.g. open design issue **#1432** / #1420), not here.

## Scope

Pure / shadow policy: approver resolution, `lifecycle.gates` defaults merge, taxonomy-aware label
matching, and approval-command simulation. No live GitHub mutations, event log (#1443), or leases (#1445).

## Gate semantics

In `lifecycle.gates`, **`true` means human approval is required** for that gate key (fail closed for
automation). **`false` means the gate does not impose that human-approval requirement** in this
bounded slice. Helpers: `gate_requires_human_review`, `stricter_autonomy_cap`.

## Configuration

- **`lifecycle.approvers`**: explicit list, or omitted on user-owned repos for owner fallback at
  runtime. Key **absent** ≠ **`approvers: null`** (explicit null fails closed). Malformed entries
  fail closed.
- **`lifecycle.taxonomy`**: optional attribute→label mapping so adopters can rename labels without
  silent misclassification. See `lifecycle_policy` docstrings.

## CLI

`gh plate process init` fills **missing** `lifecycle` keys only; it preserves stricter existing gates
and non-empty approver lists unless `--force-lifecycle` is passed.
