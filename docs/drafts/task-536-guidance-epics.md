**Task: Updated Guidance on Epics (labels, milestones, wiki on complete) + guidance architecture relief + cluster closure (#569)**

(Updating existing #536 with content from 569-guidance-architecture-relief.json, 569-580-guidance-cluster-closure.json, and related from #569.)

## Summary
- Update guidance on Epics (labels, milestones, wiki on complete).
- Enforce guidance architecture: persona thin summary only; detailed in agent_guidance.py + AGENTS; tests use key phrases not long verbatim strings (to fix persona byte budget + test coupling churn from #569).
- Close the post-0.6.1 agent guidance/Q&A/babysit stub cluster (#509-512, #521, #517 etc.) and tie off remaining #569 items (worktree/release-status, finalize, gate, Closes).
- Reinforce in AGENTS that rules are comprehensive and drift-free.

## Acceptance Criteria
- [ ] persona/agent.md and guidance.py have explicit note on thin vs detailed architecture.
- [ ] tests/test_pr_babysit.py (and similar) assert key phrases/headers, not full long strings.
- [ ] AGENTS.md updated for Q&A follow-through, babysit full loop, release status first, implemented state (#556), agent-only gate.
- [ ] The cluster of stubs are referenced as closed in fragments and docs.
- [ ] Epic guidance (labels, milestones, wiki) updated per observations.
- [ ] No repeated user corrections needed for Q&A/babysit in future sessions.

## Details from Fragments
Migration and agent_notes as in the JSONs: re-install persona after release; benefit from clarified protocols; when extending guidance add to .py + AGENTS only.

Parent #569 / #580. Implemented in polish slices + fragments.
