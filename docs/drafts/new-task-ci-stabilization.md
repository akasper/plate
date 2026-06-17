**Task: Add CI stabilization path for release review pushes (#569)**

New Task from fragment 569-ci-stabilization-path.

## Summary
Add 'stabilization' label + early skip in heavy-release job (ci.yml) for review-response / docs-only pushes on release-v* branches (reduce CI waste during finalization and feedback addressing). Feedback gate already lightweight/re-runnable on review/comment events.

## Acceptance Criteria / Migration
- [ ] ci.yml has the if/early exit for stabilization label or Documentation on release contexts; heavy steps skipped.
- [ ] Docs/AGENTS updated.
- [ ] For custom CI in downstream: adopt 'stabilization' label to keep review pushes cheap.

Agent notes: prefer stabilization label for Release PR review rounds; still run gh plate release status first + pr-babysit.

Parent: #569. For #580. Links: #532, #569, #580.

Implemented via fragment + code edit in .github/workflows/ci.yml .
