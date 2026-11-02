# Stub Issues

Part of the PLATE agent operating rules (formerly in `AGENTS.md`). The always-loaded core is [AGENTS.md](../AGENTS.md).

## Stub Issues

In PLATE, a **Stub** is an issue that still needs a lot of detail. It serves the purposes of:

1. Adding structure while working through uncertainty.
2. Serving as a memory placeholder for humans who want to make a sidenote while they are focused on another task.
3. Providing a surface for pre-planning.

Any kind of Issue — Epic, Feature, Documentation, Bug, Research, Design, Question, Audit, Migration, Release, etc. — can be a Stub. Being a stub just means that it still needs to be defined via the process.

Stubs are a normal and encouraged part of the workflow. They let the project maintain forward structure and memory even when individual items are not yet fully specified. Agents and humans should treat stubs as legitimate, first-class artifacts rather than "incomplete" in a pejorative sense.

### Marking and Working with Stubs
- An issue becomes (or remains) a stub when its description, acceptance criteria, scope, or other key details are still to be worked out.
- Existing `need:*` labels (especially `need:decision`, `need:docs`, `need:tests`, `need:design`) can indicate specific dimensions that still need work.
- The `status:stub` label (see `.github/labels.yml`) can be used to explicitly signal that an issue is intentionally in stub state. (The `status:blocked` and `status:ready-to-work` labels serve related but distinct planning-state purposes.)
- During interactive planning flows (e.g. `plate_plan_epic`), child issues are often created as stubs carrying the `need:refinement` label. The `need:refinement` semantics (deferred gates for full AC and fragments) remain valid for these planning-time stubs.

### Agent and Human Guidance
- When a user asks to "create a stub for X", "stub this out", or "make a placeholder issue", create the issue with the appropriate type label(s), link it to the relevant Epic/milestone where applicable, and leave the body with only the detail that is currently known. Do not over-specify.
- Stubs can (and should) be referenced from other issues, Epics, design docs, or agent sessions.
- Refinement of a stub happens through normal PLATE processes: comments, linked children, dedicated Research/Design work, or follow-up Q&A/contemplation.
- Agents must not treat a stub as ready for implementation work unless the stub status has been removed or the required detail has been supplied.
- When closing a stub, ensure it has a proper traceable git artifact per the Issue Artifact Rules (even if the artifact is simply "this stub was superseded by #N" or a design doc).

Stubs are one of the primary tools PLATE provides for operating effectively in the presence of uncertainty while still preserving GitHub as the single source of truth.

See Feature #351 for the discussion that produced this definition. The two Epic issues #349 and #350 were created as stubs under this understanding.
