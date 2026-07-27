# Research closeout: High-priority test coverage gaps (#364 / Epic #350)

- **Issue:** #364
- **Parent Epic:** #350 Test Coverage Audit
- **Date:** 2026-07-27
- **Status:** Closed for high-priority inventory gaps

## Question / goal

Close the high-priority gaps called out by the initial audit skeleton
(`docs/audits/test-coverage-audit-initial-inventory-2026-06-06.md`) and Research
#361: contemplation contract depth, compound ceremony flows, template payload
adopter parity, bidirectional what_next/PM proofs, and explicit Proves/Evidence
links.

## What shipped (traceable PRs)

| Gap theme | Child / PR | Proving surface |
|-----------|------------|-----------------|
| what_next / PM idle ranking | #907 / #908, #919 / #920 | `tests/test_what_next.py` |
| template_payload adopter | #917 / #918 | payload + import dry-run claims |
| Contemplation transcript + typed follow-ups | #921 / #922 | `tests/test_contemplation.py` |
| Contemplation git provenance | #923 / #924 | same |
| Contemplation mutation intents + PR draft | #925 / #926 | same |
| Contemplation mutation PR plan dry-run apply | #929 / #930 | same |
| Compound Playwright offline ceremony | #927 / #928 | `tests/e2e/compound-flows.spec.ts` |
| Closeout + Evidence links | this document + audit addendum | docs only |

## Intentionally deferred

1. **Live auto-push / `gh pr create` inside Contemplation without an injectable runner** — default remains dry-run (`apply_mutation_pr_plan(dry_run=True)`). High-risk paths require `allow_high_risk`. Follow-on: Contemplation v2.2+ / Epic #257.
2. **Live-network babysit→merge and release cut+tag+finalize apply in CI** — offline harness certifies dry paths; live apply needs secrets and is non-idempotent.
3. **Full interactive epic planning engine** — product Feature, not a pure test-gap under #364.

## Recommendation

- Close Feature #364 as high-priority gap work complete.
- Leave Epic #350 open only if remaining work is classification tooling or low-priority inventory (not re-open #364 for deferred safety items).
- Agents cite this note + audit closeout addendum when claiming #350 progress.

## Answer signal

- [x] High-priority inventory gaps mapped to proving tests and PRs
- [x] Deferred items listed with rationale and follow-on home
- [x] Design Acceptance Evidence updated for Contemplation

=== USAGE REPORT ===
tokens: 0
cost: $0.00
duration: 00:15:00
=== END USAGE REPORT ===
