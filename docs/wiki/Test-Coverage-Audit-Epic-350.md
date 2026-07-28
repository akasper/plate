# Epic #350 — Test Coverage Audit (closeout)

**Status:** Close (first slice) — all children complete (2026-07-27).  
**Milestone:** Test Coverage Audit  
**Canonical audit:** `docs/audits/test-coverage-audit-initial-inventory-2026-06-06.md`  
**High-priority gap closeout:** `docs/research/364-test-coverage-gap-closeout.md`

## Outcome

PLATE has bidirectional, inspectable proof for high-priority documented claims: classification inventory, Acceptance Evidence convention, a repeatable audit surface, and concrete gap-closure PRs for what_next/PM ranking, template_payload adopter parity, Contemplation contract depth, and offline compound ceremony e2e.

## Children (4/4)

| Issue | Type | Outcome |
|-------|------|---------|
| **#361** | Research | Inventory + classification of tests for feature-proof coverage |
| **#362** | Design | Acceptance Evidence convention for proving-test citations |
| **#363** | Feature | Repeatable test coverage / feature-proof audit surface (MCP + CLI) |
| **#364** | Feature | High-priority gap closures + closeout evidence (`status:implemented`) |

## Key proving surfaces

- `docs/research/test-classification-inventory.md`
- `docs/audits/test-coverage-audit-initial-inventory-2026-06-06.md` (#364 closeout addendum)
- `tests/test_what_next.py`, `tests/test_contemplation.py`
- `tests/e2e/compound-flows.spec.ts` + `fixtures/compound_flow_driver.py`
- Contemplation Evidence: `docs/design/contemplation-engine-contract.md`

## Residuals (not epic reopen blockers)

| Residual | Follow-on |
|----------|-----------|
| Contemplation live auto-push without injectable runner | Contemplation v2.2+ / Epic #257 |
| Live-network babysit→merge and cut+tag+finalize apply in CI | Nightly / human Task; offline harness is #364 cert |
| Continuous low-priority inventory expansion | New Features under audit tooling, not reopen #350 children |

## Agent guidance

- Prefer citing the audit closeout addendum + #364 research note when claiming coverage for v1.0 surfaces.
- Do not re-open #350 solely for deferred live-network or auto-push work.
- Classification edge cases remain human judgment (Epic original risks).

## Links

- Parent roadmap Release **#654**; wiki `V1-Autonomy-Surfaces-Epic-Closeouts.md`
- Fragments: `364-test-coverage-gap-closeout.json` and related unreleased proof slugs
