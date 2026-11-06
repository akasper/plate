# Issue lifecycle (design baseline #1420 / slice #1425)

This document records the **bounded slice** implemented in `plate_core.lifecycle_policy` for
[#1425](https://github.com/akasper/plate/issues/1425) (approvers, gate keys, shadow policy). It
does **not** replace the full lifecycle design scope in [#1420](https://github.com/akasper/plate/issues/1420)
(events, leases, wake integration, GitHub mutations).

## Configuration

- **Source of truth (machine-readable):** `.agentic/process.yml` under top-level `lifecycle:`.
- **`lifecycle.approvers`:** list of GitHub `login` strings (lowercased in code). Populated via
  `gh plate process init` (requires `gh` auth). Organization-owned repositories **must** supply
  explicit approvers (`--approvers a,b`). User-owned repositories default the token user when they
  own the repo; mismatched token user vs `owner.login` requires the explicit confirmation flag
  on the CLI.
- **`lifecycle.gates`:** boolean map; balanced defaults are defined in code (`DEFAULT_LIFECYCLE_GATES`)
  and merged on init. Keys `gate_label_downgrade`, `project_budget`, and `license` stay **human-only**
  (always treated as requiring human review in helpers — PLATE must not silently waive them).

## Runtime resolution (fail closed)

- **Explicit list present and non-empty:** use it (`resolve_runtime_approvers`).
- **Key absent, user-owned repo:** fallback to `GET /repos/OWNER/REPO` → `owner.login` (handled by
  callers that pass `repo_obj`; no literal login in source).
- **Key absent, organization-owned repo:** refuse all approval-class actions.
- **Empty list:** refuse all approval-class actions.

## Policy primitives (pure)

| Primitive | Role |
|-----------|------|
| `label_indicates_downgrade` | Detect removals of `risk:*`, `tier:*`, `need:human-review`, `need:security-review` |
| `decide_issue_label_change` | Shadow allow / deny for downgrades and non-approver `risk:critical` raises |
| `RollingCriticalRaiseTracker` | Fourth non-approver raise to `risk:critical` within a rolling hour → deny |
| `decide_approval_command` | First-line-only `/plate resume` / `/plate approve`, approver-only, `pending_write` block |
| `stricter_autonomy_cap` | Gate boolean ∩ `.plate` `autonomy.risk_tolerance` ordering |
| `match_labels_by_taxonomy` | Match `risk=`, `tier=`, issue type — not free-form taxonomy strings |
| `assert_no_path_removes_human_review` | Lightweight source scan guard (narrow module list) |

## Integration boundaries (deferred)

- **[#1374](https://github.com/akasper/plate/issues/1374)** consolidated approval engine: this slice
  does not replace checkpoint / planning / media approval modules; it exposes reusable **policy
  decisions** those engines can call later.
- **[#1398](https://github.com/akasper/plate/issues/1398)** auto-merge eligibility: `stricter_autonomy_cap`
  aligns with the documented “stricter wins” rule but does not hook `auto-merge.yml`.
- **[#1443](https://github.com/akasper/plate/issues/1443) / [#1445](https://github.com/akasper/plate/issues/1445)**
  event log and leases: out of scope; no dependency in this PR.
- **Live GitHub:** no label edits, comments, reverts, or auto-merge side effects in this slice.

## Verification

- Tests: `tests/test_lifecycle_policy_1425.py` (stdlib `unittest`).
