---
name: Address PR Feedback
description: Reply to every PR review thread, resolve it, and re-query until zero unresolved threads remain (except human-escalated items).
---

# Address PR Feedback

> Skill id: `address-pr-feedback`

Mandatory whenever you fix PR review feedback, babysit a PR, or promise "address feedback". Push fixes to the **existing** PR branch only.

## Per-thread loop

Repeat until no unresolved threads remain (see Done gate):

1. **Fetch unresolved threads** — prefer `plate_get_actionable_review_threads` / `gh plate pr babysit <N>`; include outdated threads that still show `isResolved: false`.
2. **Act** — apply the fix, apply a ` ```suggestion ` block (unless wrong or high-risk), or decline with a brief reason.
3. **Reply in-thread** — post on the thread (not only a top-level PR comment). Cite the fix commit SHA or the decline reason.
4. **Resolve** — `plate_resolve_review_thread` or `gh plate pr babysit <N> --act` (auto-resolves outdated threads after pushes). Resolve only after the reply is posted.

Human judgment (credentials, architecture, security): reply explaining the blocker, add `need:human-review`, leave the thread **unresolved**.

## Done gate (required)

Re-query unresolved threads (same fetch as step 1). **Not done** until the query returns **zero** unresolved threads, except threads explicitly escalated to a human with `need:human-review` and an in-thread comment.

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
