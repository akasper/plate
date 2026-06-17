**Task: Add "closes" positioning guidance (titles vs body) + Release ceremony foundation polish (#569)**

(Updating existing #535 with content from fragment 569-release-ceremony-foundation-polish and observations in parent #569.)

## Summary
- Add guidance for "Closes #N" positioning (in body only, not titles) per AGENTS PR title rules and release ceremony.
- Implement foundation for release ceremony polish: author-filter the feedback-resolution gate (only third-party agents + explicit CHANGES_REQUESTED), auto-collect "Closes #N, ..." block from fragment "links" arrays during `cut_release` (so one Release PR merge to main auto-closes addressed issues, fixing GitHub limitation for work on release branches).
- Enhance `gh plate release cut` output to print the block for the Release PR body.
- Enhance `gh plate release finalize` (and core) with hard-reset, gh release create from release.json, ensure next "Next Release", and notes on auto-close.
- Update AGENTS.md, CLI help, etc.

This addresses key frictions from #569: GitHub auto-close only on main, manual finalize, etc.

## Acceptance Criteria / Steps (from fragment migration + #569 observations)
- [ ] Feedback-resolution-check.yml author-filters to agent patterns / PLATE_PR_FEEDBACK_AGENTS (human comments no longer spuriously block).
- [ ] release.py has `collect_closes_block` helper and integrates it in cut_release (added to release.json and printed in next-steps).
- [ ] cli.py cmd_release_cut prints the recommended Closes block; cmd_release_finalize provides concrete commands + will wire core automation.
- [ ] AGENTS.md updated with gate semantics, release ceremony for Closes block, finalize flow.
- [ ] "Closes" guidance in titles vs body is documented (titles clean, metadata in body/sidebar).
- [ ] Tests/docs pass; fragment authored (this one).
- [ ] For #580: use in the next release cut to verify one-merge-closes.

## Migration / Agent Notes (from fragment)
See the full fragment JSON for migration_impact and agent_notes (adopt agent-only gate, use gh plate release cut/finalize, set PLATE_PR_FEEDBACK_AGENTS var if custom agents, run release status first).

Parent: #569 (ceremony frictions). For Next Release #580. Related to #112 (babysit), #532 (release labels).

Implemented via polish release slices + this fragment (code in .github/workflows/feedback-resolution-check.yml, src/plate_core/{release.py,cli.py}, AGENTS.md).
