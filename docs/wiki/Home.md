# PLATE Wiki Home

This is the source-controlled home page for the repository wiki (synced from `docs/wiki/Home.md` when wiki sync is enabled).

## Core Functionality: The PLATE State Machine

**This is the heart of the PLATE process.** It drives continuous, faithful autonomous and semi-autonomous progress across Epics, Features, Releases, Audits, Q&A, babysitting, and all other ceremonies while strictly preserving human checkpoints, atomic PR discipline, Task rules, fragments, and GitHub as the single source of truth.

### Locked Operating Model
- Project state lives in GitHub (labels, issues, PRs, `.agentic/` fragments, health signals, curiosity index, `AUTONOMOUS_MODE`, etc.).
- The orchestration agent reports state transitions (events) from the live project state.
- The MCP layer (`plate_what_next` and related surfaces) is stateless. It receives the reported transition + snapshot and returns the next steps as **ABC**: one or more tuples of `(agent_type, suggested prompt W, planned tool calls / context)`.
- The orchestration agent owns actual work state, delegation to specialists (via skills + base role prompts + returned W), execution, babysitting, and re-evaluation.
- All examples below are written for a generic "a PLATE repo" so the model is portable.

### High-Level Mapping: State Transition Events → Skills & Scripts

| State Transition Event (Input)                  | Primary Skill(s)              | Scripts / MCP / CLI Tools |
|------------------------------------------------|-------------------------------|---------------------------|
| New Epic detected/open (or planning trigger)   | design, general-purpose      | `plate_what_next` (MCP), `gh plate` (issue creation) |
| Planning complete (user/agent finished)        | general-purpose              | `gh issue create` (child tickets), `plate_what_next` |
| Work item ready (Feature / standalone)         | implement                    | `plate_what_next`, `gh plate release status`, `gh pr create` |
| PR opened or feedback received                 | pr-babysit, review           | `pr-babysit`, `gh plate pr babysit`, `plate_pr_babysit` (MCP) |
| Work item / child complete (PR merged + evidence) | orchestrator (re-eval)     | `plate_what_next`, `gh` (status checks) |
| All Epic children resolved                     | orchestrator                 | `plate_what_next`, `gh pr create` (Epic-close PR) |
| Epic-close PR human-merged                     | general-purpose (finalize)   | `git tag` / `git push --tags`, `gh release`, hard-reset scripts, `gh plate release finalize` |
| Agent session start / fresh assignment         | general-purpose / check-work | `gh plate health`, `gh plate doctor --apply`, `plate_what_next` |
| Work blocked (Question, need:human, Task rules) | general-purpose             | `gh issue create` (Task, 6-field), `plate_get_answers` / Q&A tools |
| Specialist reports action complete             | orchestrator (record + re-eval) | `plate_what_next`, snapshot/artifact updates |
| Curiosity / open Question / contemplation triggered | researcher / Q&A             | `plate_get_answers`, `gh plate qanda`, contemplation tools |
| Any PR merged (babysit clean)                  | pr-babysit + orchestrator    | `pr-babysit`, `plate_what_next`, linked issue/Epic checks |
| Audit triggered (info or test coverage)        | audit / general-purpose      | `plate_perform_information_audit`, `plate_perform_test_coverage_audit` (MCP) |
| PR clean post-babysit (autonomous self-merge eligibility) | orchestrator (guarded)     | `gh pr merge --auto --squash` (only if risk:low + guards + AUTONOMOUS_MODE + feedback-resolution) |
| Key signals change (health, fragments, curiosity, AUTONOMOUS_MODE, open Questions) | orchestrator (re-eval)     | `plate_what_next`, `gh plate health/doctor` |
| Release packaging trigger                      | orchestrator / execute-plan  | `gh plate release cut/init`, `scripts/render_release_notes.py`, versioned branch ops |
| Release PR merged (human approval + heavy CI)  | orchestrator (finalize)      | `git tag` / push, downstream triggers (`.plate/` + extensions), hard-reset, `gh release create` |

See the **full detailed catalog** (with complete "Given an agent of type..." framing from the interactive design sessions, exact pre/post conditions, and traceability to AGENTS.md sections) in:

[docs/design/what-next-mcp-state-machine-catalog.md](https://github.com/akasper/plate/blob/main/docs/design/what-next-mcp-state-machine-catalog.md)

This state machine is the central engine that makes the entire PLATE methodology executable by agents while never bypassing the human judgment gates, atomicity requirements, or GitHub-as-truth rules defined in AGENTS.md.

## Release Notes and Change Files

Link to versioned per-feature change files under `.agentic/releases/` and any generated migration guidance pages.

## Feature Documentation

- [Agent Context Map](Agent-Context-Map.md) — the canonical discovery index for "where should I look first?"
- List major feature pages and their traceability links.

## Operations and Maintenance

List setup, deployment, troubleshooting, and release pages when they exist.
