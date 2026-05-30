# Answer Model & Provenance Strategy — Design Spec

- **Issue:** #142
- **Designed by:** (populated via PR #146 babysit cycle addressing devin review threads)
- **Date:** 2026-05-30
- **Status:** Draft

## Problem

Define the canonical model for capturing, storing, and retrieving user answers to informational goals (Question issues) in a way that satisfies the four invariants from Epic #139:
- Never lose user-provided information
- The agent can reliably find previous answers
- Users can revisit, revise, or correct prior answers
- Every answer drives forward progress (new issues, artifact updates)

This is the foundational data model for the entire Q&A / Contemplation system.

## Constraints

- Must work with existing GitHub issue comments as the source of truth (primary durability)
- Must be agent-friendly (easy to parse via MCP tools and GraphQL)
- Must support both human and autonomous agent answers
- Prefer GitHub-native durability over new external storage
- Revision history without loss of original user intent
- Low friction for humans entering answers via TUI

## Design Decision

**Primary storage (source of truth): Structured GitHub issue comments on the Question issue**

Every answer (initial or revision) is appended as a comment using this template (embedded JSON for machine parsing + human readable):

```markdown
<!-- plate-answer-provenance
{
  "question_id": <number>,
  "session_id": "<uuid or gh run id>",
  "timestamp": "2026-05-30T...",
  "author": "@username|devin-ai-integration|plate-agent",
  "source": "qanda-tui|cli|copilot-cli|direct-comment",
  "revision_of": <prior_comment_databaseId|null>
}
-->

**Original Question (verbatim):** 
<quote>

**Answer (verbatim user input):** 
<full text>

**Additional Context / Attachments:** 
<if any>

**Provenance / Session Notes:** 
<agent reasoning excerpt, linked MCP calls, etc.>
```

The full transcript of the Q&A exchange is always preserved in the issue timeline.

**Secondary committed artifact (for fast local/agent lookup, optional but recommended):**

- `docs/curiosity/answers/<kebab-slug-from-question-title>.md` (append-only log mirroring the key provenance + excerpt + link to GitHub comment)
- Or a central index `docs/curiosity/answers-index.json` (or .yml) with { "questions": [ {id, title, latest_answer_excerpt, comment_ids: [...], last_updated} ] }

Agents (via MCP tools in #145) and humans prefer the committed form for speed when the repo is cloned; GitHub comments remain authoritative. On any answer ingest, both are updated atomically in the same PR/commit where possible.

**Revision / correction workflow:**

- New answer comment always created (append-only)
- `revision_of` points to the databaseId of the comment being corrected
- Latest effective state for a Question is derived by replaying the comment chain (last non-superseded answer wins for most purposes)
- Stale follow-up issues created from a revised answer may be closed with explanation linking to the correction comment

**Query / retrieval patterns for agents:**

- GitHub GraphQL: `repository.issue(number: Q).comments(...)` filtered by the plate-answer-provenance marker + parse JSON
- REST search: `q=plate-answer-provenance+repo:owner/name+in:comments`
- MCP tools (see sibling #145): `plate_list_open_questions`, `plate_ingest_answer` (which triggers model write + Contemplation contract)
- Local: parse the committed docs/curiosity/ file or index for <1s lookup in cloned repo

**Migration / backfill:**

- Existing historical answers on Questions can be backfilled by a one-time `gh plate` or script that re-processes closed Questions, emitting the structured comments (preserving original text).
- Label migrated items `curiosity:migrated-answer`.
- No data loss: original comments remain.

**Integration with Contemplation (#143):** The model is the storage layer; Contemplation contract dictates *when* and *what* to write on answer receipt.

## Alternatives Rejected

| Alternative | Why Rejected |
|-------------|--------------|
| Purely ephemeral in agent context window | Violates "never lose" invariant; no persistence across sessions or for other agents/humans |
| Only in GitHub comments with no committed artifact | Current weak state; poor findability/performance for agents doing synthesis across many Questions (see research #140) |
| Full custom database or Notion-style system | Violates PLATE "GitHub as source of truth" principle and durability guarantees |
| Using GitHub Discussions instead of issue comments | Less structured linking to Questions, harder to enforce templates/labels, poorer MCP/GraphQL ergonomics |

## Artifact

- Comment template + JSON schema (above)
- Recommended committed artifact format + example directory layout
- Agent query patterns (GraphQL + MCP pseudocode)
- Migration script outline + backfill considerations
- Example answers drawn from the research inventory (to be expanded with #140 artifact)

## Open Questions

- Use of GitHub Projects v2 fields for denormalized "answer_status" / priority to speed queries (vs. comment scan)
- Indexing / search strategy when repo accumulates hundreds of open Questions (future scalability)

## Acceptance Evidence

- Given any Question number, an MCP call or `gh` query returns the complete lossless answer history (all revisions) in < 3s
- A revision comment correctly links via revision_of and does not alter prior comments
- Both GitHub comments and the optional committed docs/curiosity/ form stay in sync after ingest
- Backfill of 5+ historical Questions succeeds without data loss or duplication

This design satisfies Design issue #142 scope and decision criteria. It is informed by the research inventory in #140 (pending commit of `docs/research/curiosity-qanda-inventory.md`). All content changes pushed to the existing PR #146 branch per babysitting rules. Cross-references sibling designs #143 (contract), #144 (UX), #145 (surfaces).