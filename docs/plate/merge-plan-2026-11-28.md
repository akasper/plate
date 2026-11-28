# Merge readiness plan — 2026-11-28

Live sweep of open pull requests **#1516–#1547** in `akasper/plate`. Pinned PR heads were not rebased or force-pushed. Merge cleanliness was tested locally by merging each PR head onto its **current base tip** in detached scratch worktrees (not pushed).

**Integration branch tips at sweep time**

| Branch | Tip SHA |
| --- | --- |
| `release-minor` | `04edd4898713cde9f1944154b25da9f5d66d9fd7` |
| `release-patch` | `12f22e61f4162b44aa66971d83e26d2537d9d7f9` |

**Numbers with no open PR in range:** #1525, #1527, #1529, #1531, #1537 (tracked as issue; implementation PR is #1540), #1539, #1542, #1543 (issue; implementation PR is #1544), #1545, #1546 (issue; implementation PR is #1547).

---

## Recommended merge order

Order respects declared stacks. **Features** land on `release-minor`; **bugs** on `release-patch`. Stacks should merge bottom-up; after each parent merges to its integration branch, retarget children (see next section).

### Track A — `release-patch` (can proceed in parallel with Track B)

1. **#1516** — template E2E ffmpeg / apt refresh (#1515)
2. **#1518** — marker merge base + safe import (#1477)
3. **#1519** — babysit `--act` hardening (#1474)
4. **#1520** — budget / delegation persistence (#1476)
5. **#1521** — auto-merge eligibility via `.plate` (#1471) — blocked on maintainer CODEOWNERS handle (S7)
6. **#1523** — release ceremony hardening (#1488)

### Track B — `release-minor` foundations

7. **#1522** — CI baseline (#1478)
8. **#1526** — pr-gates unittest policy (#1182) — **after #1522** (`pr-gates` red is structural: gate modules ship in #1522; expect green after #1522 lands)
9. **#1517** — AGENTS / factual docs (#1479)
10. **#1528** — adoption health (#1193) — **after #1517**

### Track C — MCP registry stack (on #1524)

11. **#1524** — MCP registry, confinement, stdio loop (#1475)
12. **#1540** — MCP tools/list catalog drift (#1537) — **on #1524**
13. **#1544** — explicit MCP handler map (#1543) — **on #1540**
14. **#1530** — `gh plate evidence` / `--attach` (#1051) — **on #1524** (may follow #1540 or merge in parallel once #1524 is green; stack base is the same)

**Fixture regeneration checkpoint (MCP tool count):** After **#1544** merges (with **#1524** and **#1540**), the live MCP catalog in code reflects **211** tools in `tools/list` with `PLATE_MCP_TOOL_PROFILES=all`. The public-surface stack (#1536 / #1541 / #1547) still documents and fixtures **209** tools from the inventory written before the MCP catalog fixes. On the integration branch, run `python3 scripts/regenerate_public_surface_stable.py` (and update `docs/plate/research/public-surface-inventory.md` catalog size if needed) **before** merging **#1541** and **#1547**, and again after **#1547** if loaders change classification.

### Track D — public surface / compat stack (on #1536)

15. **#1536** — public surface inventory (#1056); PR type label is **Documentation** (prior `Research` label mismatch cleared on the PR)
16. **#1538** — CLI/MCP stable reference + drift check (#1068) — **on #1536**
17. **#1541** — compat contract tests (#1058) — **on #1536** (regenerate fixture after Track C checkpoint); **blocked on re-review** after must-fix at `1a06a415` (head `79e51c24` under review)
18. **#1547** — consolidate loaders into `plate_core` (#1546) — **on #1541**; **hold until #1541 clears re-review**

### Track E — user docs on `release-minor` (coordinate README)

19. **#1535** — token-scope reference (#1061) — green; awaits human security review
20. **#1534** — `SECURITY.md` (#1060) — **ready once `pr-gates` reruns green** (private vulnerability reporting enabled; agent review thread resolved)
21. **#1532** — concepts guide (#1067) — open questions in PR body
22. **#1533** — quickstart (#1066) — 3 unresolved review threads, `pr-gates` failure

Prefer merging **#1517** and **#1528** before **#1532** / **#1533** so adoption and AGENTS prose is stable. Local sequential simulation (1517 → 1528 → 1532 → 1533 → `release-minor`) merged without conflicts today; all three still edit `README.md` relative to the same merge-base, so integration order may still need manual README reconciliation if bases move.

---

## Retargets after each parent lands

| After parent merges to… | Child PR | Current base branch | Retarget base to |
| --- | --- | --- | --- |
| `release-minor` | **#1526** | `cursor/ci-baseline-1478-4a75` | `release-minor` |
| `release-minor` | **#1528** | `cursor/docs-reconcile-1479-5605` | `release-minor` (or keep stacked through merge train) |
| `release-minor` | **#1530**, **#1540** | `cursor/mcp-registry-confinement-1475-81f3` | `release-minor` |
| `release-minor` | **#1544** | `plate/1537-mcp-drift` | `release-minor` |
| `release-minor` | **#1538**, **#1541** | `plate/1056-public-surface-inventory` | `release-minor` |
| `release-minor` | **#1547** | `plate/1058-compat-contract` | `release-minor` |

Until retargeted, children remain valid stacked PRs against parent branch heads; all stack parent tips matched child merge-base at sweep time (not stale).

---

## Per-PR readiness table

**Base stale:** `yes` if the remote base tip has commits not contained in the PR head (`git merge-base --is-ancestor`). **Merge clean:** local `git merge` of base tip into head in a scratch worktree. **Rebase:** local `git rebase` onto base tip in the same worktree.

| PR | Title (short) | Head SHA | Base | Base stale | Merge clean | Rebase OK | CI | Unresolved threads | Linked issue(s) | Stack parent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1516 | Template E2E ffmpeg apt update | `963aea28eccf77b72f25ee1975227f6d603831d1` | `release-patch` | no | yes | yes | green | 0 | #1515 | — |
| 1517 | AGENTS links + factual drift | `67f667a161574cccb51d7a3ff3258d06927be285` | `release-minor` | no | yes | yes | green | 0 | #1479 | — |
| 1518 | Marker merge + safe import | `87e4113a5b1072473f96b447410f68630a9eca6c` | `release-patch` | no | yes | yes | green | 0 | #1477 | — |
| 1519 | Babysit `--act` hardening | `3de4025bf65416c9956389837a93212e532738e3` | `release-patch` | no | yes | yes | green | 0 | #1474 | — |
| 1520 | Budget / delegation persistence | `0b35f42acfa0501584bf85448392b493ab3587c8` | `release-patch` | no | yes | yes | green | 0 | #1476 | — |
| 1521 | Auto-merge `.plate` eligibility | `692346d5391fc9754cb4eb65a6db7202e63cf0c8` | `release-patch` | no | yes | yes | green | 0 | #1471 | — |
| 1522 | CI baseline | `f24781a045031ccf17f762964c34f1397c11ce8f` | `release-minor` | no | yes | yes | green | 0 | #1478 | — |
| 1523 | Release ceremony hardening | `cb69ed344a12607cc6b613714e812f625b8ecc60` | `release-patch` | no | yes | yes | green | 0 | #1488 | — |
| 1524 | MCP registry + confinement | `dab6f2d4cab4605b5e20886dbdad1182f16b2067` | `release-minor` | no | yes | yes | green | 0 | #1475 | — |
| 1526 | Deterministic pr-gates checks | `437192a1d7dd9655a98b3174fe4a3e4471bf4966` | `cursor/ci-baseline-1478-4a75` | no | yes | yes | structural red (`pr-gates`; modules from #1522) | 0 | #1182 | #1522 |
| 1528 | Adoption health | `35daed3729a2143256434e82d6bd2c4cff92db0c` | `cursor/docs-reconcile-1479-5605` | no | yes | yes | green | 0 | #1193 | #1517 |
| 1530 | `gh plate evidence` wrapper | `99c8fdf9c3f015f256941e4ea0d1496a9f9f02b0` | `cursor/mcp-registry-confinement-1475-81f3` | no | yes | yes | red (`test`) | 0 | #1051 | #1524 |
| 1532 | PLATE concepts guide | `875f60d7a1e5040066d4ab7d8dbadc43e67e5e7c` | `release-minor` | no | yes | yes | green | 0 | #1067 | — |
| 1533 | User quickstart | `7f41f442a9e2f3c8b5cbcaa101af638fe6be04e7` | `release-minor` | no | yes | yes | red (`pr-gates`) | 3 | #1066 | — |
| 1534 | `SECURITY.md` | `a25206eb020f6d88296668b6aea6fccda5911f54` | `release-minor` | no | yes | yes | ready once `pr-gates` green | 0 | #1060 | — |
| 1535 | Token-scope reference | `c653e12a800b8d7785772f88eff2b89921468908` | `release-minor` | no | yes | yes | green | 0 | #1061 | — |
| 1536 | Public surface inventory | `6c0a1eb9a0f023c50e0140f7bd734bd67c81661d` | `release-minor` | no | yes | yes | green (Documentation label) | 0 | #1056 | — |
| 1538 | CLI/MCP stable reference | `723933d6c8e887dfd7cef91167307c9fcf9ef477` | `plate/1056-public-surface-inventory` | no | yes | yes | green | 0 | #1068 | #1536 |
| 1540 | MCP tools/list drift fix | `5c99a82f0e7dba6a644ef22b549e4294e3a70c97` | `cursor/mcp-registry-confinement-1475-81f3` | no | yes | yes | green | 0 | #1537 | #1524 |
| 1541 | Public-surface compat tests | `79e51c24612dc1bc1566668a75c989ebef2fa491` | `plate/1056-public-surface-inventory` | no | yes | yes | blocked on re-review | 0 | #1058 | #1536 |
| 1544 | MCP handler map refactor | `f09970d78f73d6a5505ddc634567ef3b09d500d6` | `plate/1537-mcp-drift` | no | yes | yes | green | 0 | #1543 | #1540 |
| 1547 | Public-surface loader consolidation | `00314184ad5e25d285c88f0b1e6badb371523fb7` | `plate/1058-compat-contract` | no | yes | yes | holding (#1541) | 0 | #1546 | #1541 |

GitHub `mergeStateStatus` values: `BLOCKED` or `UNSTABLE` on several rows reflect missing human approval or label-check failures, not necessarily merge conflicts. Every open PR in the table is `mergeable: MERGEABLE` on GitHub at sweep time.

No PR in range had a stale base at sweep time; no local merge or rebase conflicts were observed against the recorded base tips.

---

## Likely `README.md` overlap (#1528, #1532, #1533)

- **#1528** (`cursor/adoption-health-1193`) changes adoption-related README sections.
- **#1532** and **#1533** each change `README.md` relative to the shared merge-base with `release-minor`.
- A ordered local merge train (1517 → 1528 → 1532 → 1533) applied cleanly on the snapshot `release-minor` tip; if integration order differs or other doc PRs land first, expect to reconcile the install/adoption/quickstart sections manually.

---

## Maintainer decisions and external gates

| Item | Context |
| --- | --- |
| **#1535** human security review | PR carries `need:security-review`; content is green in CI. |
| **#1538** CI `--check` | Open question whether `ci.yml` should run `scripts/generate-cli-mcp-reference.py --check` on every PR. |
| **`plate_release_media_*` experimental** | **#1536** inventory lists media MCP tools under experimental/evolving surface; confirm 1.0 stable vs experimental classification. |
| **#1532 open docs questions** | Label registry vs issue types, epic-close base branch, semver enforcement, user-docs path layout, stub clearance (#1067). |
| **#1533 open docs questions** | SPEC vs README MCP install line, stub #1066 refinement, CONTRIBUTING branch model, first Q&A seed path, bootstrap time budget (15 vs 30 minutes). |
| **#1536 / #1541 open questions** | Autonomy CLI vs MCP naming; whether `regenerate_public_surface_stable.py --check` belongs in CI on every PR. |
| **#1521 CODEOWNERS** | Scope item S7 (real CODEOWNERS handle) intentionally deferred in PR body. |
| **#1116 stub** | Adopt/bootstrap defects (`status:stub`, `need:refinement`); not in the #1516–#1547 PR window—scope and landing track still open (#1522 CI baseline touches adjacent surfaces). |
| **#1008 refinement drafts (#1031–#1038)** | Epic #1008 and child issues remain open with `need:refinement` / stub status; refinement drafts for #1031–#1038 are not yet posted on the tracker. |
| **v0.12.1 / v0.13.0 release cuts** | Not represented in PRs #1516–#1547; release ceremony work (#1523) is patch-track only. Schedule cuts after integration branches absorb the above stacks. |

---

## Sweep method

- Metadata: `gh pr view`, GitHub `statusCheckRollup`, GraphQL `reviewThreads`.
- Staleness: `git merge-base --is-ancestor origin/<base> <head>`.
- Merge/rebase probes: ephemeral `git worktree` per head; no pushes.
- Sweep date: 2026-11-28 (UTC).