**Task: Implement minimal PLATE Issue states (status:implemented on release-branch merge) (#556)**

New Task from fragment 556-issue-states-minimal. Child of #556 stub Epic.

## Summary
Minimal support: add status:implemented label; workflow step (in pr-issue-link-check.yml) that marks linked issues on merge to release-* branches (distinguishes implemented-in-RC from released-to-main); surface notes in epics.py, AGENTS, persona + updates.

Enables tracking work landed on release branches before final Release PR to main.

## Acceptance Criteria
- [ ] .github/labels.yml has status:implemented (color, desc).
- [ ] Workflow marks on release branch merges (Closes detection or GraphQL).
- [ ] epics.py / health / CLI surfaces note or report the state.
- [ ] AGENTS.md, persona updated.
- [ ] Migration guidance followed for downstream (sync label, use in queries like gh issue list --label status:implemented).
- [ ] Queries like "which Bugs are implemented in this RC but not yet shipped?" possible.

From fragment: lifecycle open -> implemented (release merge) -> closed/released (main+tag).

Parent Epic #556. For Next Release #580. Related #569.

Implemented via fragment + edits to labels.yml, pr-issue-link-check.yml, epics.py, AGENTS.md, persona.
