---
name: Address PR Feedback
description: Reply to every PR review thread, resolve it, and re-query until zero unresolved threads remain (except human-escalated items).
---

<!-- PLATE-GENERATED:BEGIN skills-surface -->
<!-- Do not edit generated skill surfaces manually. -->
<!-- Source of truth: src/plate_core/data/baseline_catalog.yml -->
<!-- Regenerate: python3 scripts/generate-plugin-skills.py -->

# Address PR Feedback

> Skill id: `address-pr-feedback`
> Generated from the baseline catalog. Regenerate with `python3 scripts/generate-plugin-skills.py`.

Reply to every PR review thread, resolve it, and re-query until zero unresolved threads remain (except human-escalated items).

**Owning agents:** software-engineer, ci-engineer

## Inputs

- PR number
- Unresolved review threads (via plate_get_unresolved_review_threads or GraphQL fallback)

## Outputs

- In-thread replies with commit SHA or decline reason
- Resolved review threads
- Zero-unresolved re-query confirmation

## Examples

- After pushing a fix for Copilot feedback, run the per-thread loop until the re-query returns zero unresolved threads.

<!-- PLATE-GENERATED:END skills-surface -->

## Per-thread loop

Repeat until no unresolved threads remain (see Done gate):

1. **Fetch unresolved threads** — use `plate_get_unresolved_review_threads` (every `isResolved: false`, including outdated) or the GraphQL fallback below. Do **not** use `plate_get_actionable_review_threads` for fetch/done gate (it skips outdated threads).
2. **Act** — apply the fix, apply a ` ```suggestion ` block (unless wrong or high-risk), or decline with a brief reason.
3. **Reply in-thread** — post on the thread (not only a top-level PR comment). Cite the fix commit SHA or the decline reason.
4. **Resolve** — `plate_resolve_review_thread` with that thread's ID (or the `resolveReviewThread` mutation below) **only after** that thread's reply. Do **not** use `gh plate pr babysit --act` as a per-thread resolver (`--act` bulk-closes outdated threads without checking replies).

Human judgment (credentials, architecture, security): reply explaining the blocker, add `need:human-review`, leave the thread **unresolved**.

## Done gate (required)

Re-query with `plate_get_unresolved_review_threads` (same contract as step 1). **Not done** until the query returns **zero** unresolved threads, except threads explicitly escalated to a human with `need:human-review` and an in-thread comment.

## Pre-merge recheck (#1234)

Immediately before any merge or auto-merge, fetch fresh PR state again. Do **not** merge when the PR is BEHIND, DIRTY, or CONFLICTING relative to its base. If the base branch moved after the last green CI run and the new base commits touch files this PR modifies, sync the branch, push, and wait for checks to pass again. Never use `--admin` or other bypass flags that skip protection or required checks (especially on permissive bases like `release`). (Guidance adapted from tstack, MIT, Theo Browne; see #1232/#1234.)

## Keep review loops small (#1234)

Fix comments that identify real bugs in the intended use case. Decline scope creep—extra tests, rare edge cases, minor performance tweaks, or broad compatibility not required for this PR—with a clear in-thread reason, resolve the thread, and list each declined item as a follow-up. When choosing between fixes, prefer deleting or narrowing code over adding layers. (Same tstack credit as above.)

## GraphQL fallback (helpers unavailable)

Use **only** these exact patterns — no jq/mktemp/sed wrappers.

**List unresolved threads** (paginate with `pageInfo.endCursor` / `hasNextPage`):

```bash
gh api graphql -f query='
query($owner:String!,$name:String!,$number:Int!,$after:String) {
  repository(owner:$owner,name:$name) {
    pullRequest(number:$number) {
      reviewThreads(first:100, after:$after) {
        pageInfo { hasNextPage endCursor }
        nodes { id isResolved isOutdated path
          comments(last:5) { nodes { databaseId body url author { login } } }
        }
      }
    }
  }
}' -f owner=OWNER -f name=REPO -F number=PR
```

**Reply in-thread:**

```bash
gh api graphql -f query='
mutation($threadId:ID!,$body:String!) {
  addPullRequestReviewThreadReply(input:{pullRequestReviewThreadId:$threadId, body:$body}) {
    comment { url }
  }
}' -f threadId=THREAD_NODE_ID -f body='Fixed in abc1234: …'
```

**Resolve thread:**

```bash
gh api graphql -f query='
mutation($threadId:ID!) {
  resolveReviewThread(input:{threadId:$threadId}) {
    thread { id isResolved }
  }
}' -f threadId=THREAD_NODE_ID
```

