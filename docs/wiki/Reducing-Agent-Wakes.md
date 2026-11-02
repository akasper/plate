# Reducing agent wakes (#1335)

Child of Epic #1327 (agent crews). Use this page when you orchestrate multiple agents, run long babysit watches, or delegate narrow jobs. The goal is fewer **wake events** (each time an agent session starts or resumes because something changed) without hiding real blockers.

Related: [PR babysit wake summary](PR-Babysit-Wake-Summary.md), [Quiet Agents (#456)](Quiet-Agents-Epic-456.md), `docs/design/cost-control-narrow-delegation-packets.md`.

## Principles

1. **Batch status messages.** Workers report progress on a schedule or at phase boundaries (for example “tests green”, “pushed”, “blocked on human”), not after every tool call. The orchestrator merges worker lines into one update for the human or parent agent.
2. **Send digests, not per-step updates.** One summary per tick or phase beats many one-line pings. Include only deltas since the last digest: new failures, new review threads, merge-state changes.
3. **No broadcasts to all agents.** Route messages to the one agent that must act. Do not @-mention or wake every crew member for CI noise, bot comments, or status that only the babysitter needs.
4. **`priority: true` only when the receiver must act.** In handoffs, subscriptions, and internal message envelopes, mark high priority only when waiting blocks the crew or risks merge/regression. Routine progress stays normal priority so schedulers can coalesce work.
5. **Keep briefs short.** Delegation text should be a narrow task packet (summary, success signal, scope, authoritative paths)—not a copy of `AGENTS.md`. Point to scoped discovery (`gh plate context show`, catalog agents/skills) instead of inlining policy.
6. **Static rules first, volatile job details last.** Put stable instructions and constraints at the **top** of prompts and crew briefs; put branch name, date, PR number, diff summary, and file lists at the **bottom**. Hosts that prefix-cache system and user content reuse the stable prefix across jobs, which cuts token cost on repeated crew turns. (See [cache-friendly prompt ordering](https://x.com/undefinedki/status/2116278013398557171)—same idea expressed independently here: shared prefix, variable suffix.)
7. **Trim the tool set per job.** Give each agent only MCP tools and skills required for that task (babysit-only vs implement-only vs research-only). Extra tools increase schema noise and invite exploratory calls that cause wakes.

## Crew brief template

Copy and fill the volatile block last; keep the static block identical across jobs when possible.

```markdown
<!-- STATIC — do not edit per job; maximizes prompt cache hits -->

## Role
You are the {role} for this crew. Follow PLATE quiet operations: terse bullets in chat, GitHub comments only on forward progress.

## Wake rules
- Do not wake other agents; report to the orchestrator only.
- Batch status; no per-step pings.
- Set priority true only when the receiver must act now.

## Tool budget
Allowed: {comma-separated MCP tools / skills}
Out of scope: {forbidden actions}

## Static references
- Process discovery: `gh plate context show process`
- Release base: run `gh plate release status` before any PR targeting decision.

<!-- VOLATILE — per job; keep after static block -->

## Job
- Task: {one sentence}
- Success: {observable done signal}
- PR / issue: #{n} (if any)
- Branch: `{branch}` (base `{base}` from release status)
- As-of: {ISO date}
- Diff / focus: {paths or summary}
- Working set: {files or grep hints}
```

Orchestrators should paste or generate the static section once per agent type and append only the volatile section per assignment.

## Pilot metric: wakes per merged PR

**Definition (pilot):** Count one **wake** each time an agent run **starts meaningful work** on that PR because of an external signal—not because the same session continued thinking. Include:

| Source | What counts as one wake |
|---|---|
| `gh plate pr babysit --watch` | Each time the watch loop records a wake after an actionable delta (`record_wake` in the cap ledger—see below). |
| Babysit without watch | Each distinct agent session invoked to babysit or fix that PR (orchestrator logs or host run id). |
| Crew handoffs | Each delegation that starts a **new** worker session on the same PR (not an in-thread reply in the same session). |

Exclude: probe ticks that back off quietly, non-actionable wake summaries (`is_actionable` false), and human-initiated retries in the same session without a new trigger.

**Pilot target:** **≤ 6 wakes per merged PR** for typical Feature/Bug PRs (single implementer + babysit to green). Track median and p90 over the pilot window; investigate PRs above **10** wakes as process bugs (broadcast loops, per-step status, or full PR reloads every tick).

### How to count (babysit watch)

1. While the PR is open, the watch loop persists a cap ledger under `.agentic/babysit/` (see `plate_core.pr_watch_caps.caps_path`).
2. Before or after merge, read `wakes` from the ledger JSON, or run:

   ```bash
   gh plate pr babysit <PR_NUMBER> --watch --status
   ```

   The status line reports usage like `wakes 3/10, 2.5h/12h`.

3. For crew pilots without watch, keep a short table in the Epic comment: PR number, merge date, wake count, notes (broadcast fixed, digest adopted, etc.).

4. **Normalize:** `wakes_per_merged_pr = sum(wakes for merged PRs in window) / count(merged PRs)` for PRs labeled Feature or Bug in the pilot milestone.

Improvement checks: fewer cap-ledger wakes after adopting digests and no-broadcast rules; fewer babysit GraphQL reloads when following [PR babysit wake summary](PR-Babysit-Wake-Summary.md).

## Checklist before adding a wake

- Can this update wait for the next digest boundary?
- Is exactly one agent the right receiver?
- Is `priority: true` required, or is normal priority enough?
- Does the brief duplicate static rules that should live in the cached prefix?
- Does this agent need fewer tools for this job?
