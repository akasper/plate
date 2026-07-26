# Quiet Agents (Epic #456) — outcomes summary

**Status:** **Closed** — children #457/#458 complete; closeout docs on `release` (2026-07-26).  
**Parent context:** Long-running autonomous loops (`/loop`, babysit watch, autonomy cycles) must stay readable and low-noise without weakening traceability.

## Problem

Agents were flooding terminals with long dumps and posting no-op GitHub comments during monitoring turns, which made overnight loops hard to review and burned context.

## Delivered children

| Issue | Type | Outcome |
|---|---|---|
| **#457** | Feature | `QUIET_OPERATIONS_GUIDANCE` in `agent_guidance.py`; plate persona Behavior + Special modes; baseline catalog quiet constraints; light what_next/MCP prompt discipline |
| **#458** | Documentation | Audit `docs/research/quiet-agents-audit.md`; AGENTS.md cross-refs; process fragment `quiet-agents-guidance` (v0.6.0) |

Closeout evidence (AC maps): `docs/migration/457-458-quiet-agents-closeout.md` (PR #809).

## Operating rules (durable)

1. **Terminal / loops:** only a bullet list of one-brief-sentence items.
2. **GitHub comments:** only on verifiable forward progress or defined human checkpoints; engine markers exempt (`PLATE-AUTONOMY-CYCLE`, `PLATE-PROCEDURE-RUN`, USAGE REPORT).
3. **Q&A presentation:** minimal front matter unless the question is about process.
4. **Prefer MCP structured data** over raw CLI dumps in agent turns.

Primary sources: `plugin/agents/plate.agent.md`, `src/plate_core/agent_guidance.py` (`quiet_operations`), AGENTS.md babysit quiet note, `#480` autonomy_loops guidance.

## Non-goals preserved

- USAGE REPORT on Feature/Question closure still required.
- Issue Artifact Rules, contemplation markers, and human Task rules unchanged.
- No weakening of feedback-resolution or release ceremony human gates.

## Follow-ons (out of this epic)

- Further cost/context trims and persona thinness under autonomy/PM epics (#470, #660).
- Agent collab docs #509–#512 closed via guidance + research note (PR #825).

## Links

- Epic #456
- Feature #457, Documentation #458
- Fragment: `.agentic/releases/v0.6.0/fragments/quiet-agents-guidance.json`
- Research: `docs/research/quiet-agents-audit.md`
