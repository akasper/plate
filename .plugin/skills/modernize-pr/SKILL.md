---
name: Modernize PR
description: Decide whether a stale pull request still belongs, then rebase safely in an isolated worktree when modernization is warranted.
---

<!-- PLATE-GENERATED:BEGIN skills-surface -->
<!-- Do not edit generated skill surfaces manually. -->
<!-- Source of truth: src/plate_core/data/baseline_catalog.yml -->
<!-- Regenerate: python3 scripts/generate-plugin-skills.py -->

# Modernize PR

> Skill id: `modernize-pr`
> Generated from the baseline catalog. Regenerate with `python3 scripts/generate-plugin-skills.py`.

Decide whether a stale pull request still belongs, then rebase safely in an isolated worktree when modernization is warranted.

**Owning agents:** software-engineer, ci-engineer

## Inputs

- PR number
- PR goal, diff, reviews, linked issues, and base-branch changes since the branch diverged

## Outputs

- One verdict (MODERNIZE, REWORK, or CLOSE) with evidence
- For MODERNIZE only — rebase result, range-diff summary, and push plan (no merge/close by the agent)

## Examples

- An months-old feature PR on release still matches the linked issue; verdict MODERNIZE, rebase onto current base, range-diff, force-with-lease push.
- A fix duplicated on main; verdict CLOSE with links; stop without closing the PR yourself.

<!-- PLATE-GENERATED:END skills-surface -->

## Authority (non-negotiable)

- **Never close and never merge a pull request on your own.** A **CLOSE** verdict is a recommendation only; the repository owner must explicitly approve closing (per AGENTS.md human checkpoints).
- **Never change the PR base branch** and **never widen scope** (no drive-by fixes, no retargeting, no scope expansion).
- **Use an isolated git worktree** for every git operation in this skill (`cleanup_git_locks()` + `verify_worktree_is_isolated()` or equivalent before worktree add/rebase/push; never use the main checkout). Remove the worktree when finished.
- **No user trigger phrase overrides AGENTS.md approval gates** (merge, close, base change, or scope change still require human judgment).

(Workflow ideas adapted from t3dotgg/tstack `modernize`, MIT, Theo Browne; see #1232/#1235. Wording here is PLATE-original.)

## Step 1 — Understand before touching history

Inspect the PR (cheap GitHub first):

1. `gh pr view <N>` — title, body, base ref, head ref, linked issues, merge state.
2. Diff and intent — `gh pr diff <N>` (or `--name-only` first); read linked issue acceptance criteria.
3. Review signal — open comments, review summaries, unresolved threads (use **`address-pr-feedback` skill** if feedback must be cleared separately).
4. Base drift — commits on the base since the PR diverged (`gh pr view <N> --json baseRefName,headRefName,commits` and `git log` / compare on the integration branch).

A clean rebase alone does **not** prove the PR still belongs. Decide first.

## Step 2 — One verdict with evidence

Post a concise summary (PR comment or session output) with exactly one verdict:

| Verdict | Meaning | Next step |
| --- | --- | --- |
| **MODERNIZE** | Still useful and the right shape for the linked intent. | Continue to Step 3 (rebase path). |
| **REWORK** | Still useful, but the approach or diff shape is wrong. | Describe the smallest rewrite (files/approach); **stop** — no rebase, no push. |
| **CLOSE** | Superseded, obsolete, or not worth finishing. | Cite evidence (merged elsewhere, abandoned issue, contradicts current direction); **stop** — do **not** run `gh pr close`. |

Format the verdict line so it is machine-readable, e.g. `Verdict: MODERNIZE` (helpers in `plate_core.modernize_pr` accept these tokens).

## Step 3 — MODERNIZE only: rebase, verify, push

Skip this section for REWORK or CLOSE.

1. **Record pre-rebase head SHA** — `PRE_HEAD=$(git rev-parse HEAD)` on the PR branch in the worktree before rebase.
2. **Rebase onto the existing base** — do not change base; resolve conflicts without scope creep.
3. **Run targeted checks** — prefer cheap verification aligned with the diff (not full-suite by default unless required).
4. **Compare history** — after a successful rebase, run range-diff against the pre-rebase tip:

   ```bash
   git range-diff <base>...<PRE_HEAD> <base>...HEAD
   ```

   Use `plate_core.modernize_pr.git_range_diff_argv(base=..., pre_rebase_head=PRE_HEAD, post_rebase_head=HEAD)` when building argv in automation. Investigate unexpected commit reordering or dropped commits before pushing.

5. **Push with lease on the old tip** — only after range-diff review:

   ```bash
   git push <remote> <branch> --force-with-lease=refs/heads/<branch>:<PRE_HEAD>
   ```

   Use `plate_core.modernize_pr.git_push_force_with_lease_argv(...)` for the exact argv. Never `--force` without lease; never push from the main checkout.

6. **Stop before merge** — modernization ends at an updated branch and green-enough checks; human review and merge follow normal AGENTS.md gates (including pre-merge recheck #1234).

## Done gate

- REWORK or CLOSE — verdict + evidence recorded; no git history rewrite; no close/merge by the agent.
- MODERNIZE — rebase complete, range-diff reviewed, `--force-with-lease` push succeeded using `PRE_HEAD`; PR still open awaiting human merge approval.

