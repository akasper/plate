# Research: Source-of-truth hierarchy and owner-vision intake for SPEC auditing

- **Issue:** #336
- **Epic:** #335 (SPEC auditing)
- **Researched by:** plate agent session (akasper/plate)
- **Date:** 2026-07-26
- **Status:** Completed (feeds Design #337; aligns shipped #338/#339/#340)

## Research Question

Which artifacts are authoritative for different classes of SPEC statements, how should owner vision be captured explicitly, and how should conflicts between intent, implementation evidence, and historical documentation be resolved so the SPEC audit engine remains high-signal?

## Sources (repository-primary)

| Source | Path / surface | Role in this research |
|---|---|---|
| Product intent header | `SPEC.md` | Declares human-owned, agent-assisted desired future state |
| Process contract | `AGENTS.md` | Authority model; issue→artifact mapping; human checkpoints |
| Mission / strategic goals | `docs/wiki/Goals.md` | High-level mission for Information Audits (#218/#224) |
| Verified reality | `CURRENT.md` (when present) | Implementation truth vs SPEC intent |
| Release evidence | `.agentic/releases/unreleased/*.json` + versioned dirs | Machine-readable “shipped or staged” capability evidence |
| Autonomy design | `docs/design/autonomous-plate-engine.md` | Human gates for SPEC/AGENTS/workflow changes |
| Information Audit design | `docs/design/information-audit-contract.md` | Goals → Questions intake model |
| Shipped audit plane | `src/plate_core/spec_audit.py` (#338–#340) | v1 findings kinds and health/what_next exposure |
| GitHub planning truth | Issues, milestones, labels, PR bodies | Work queue and acceptance provenance (not product intent) |

## Findings

### 1. Candidate evidence sources and what they can / cannot prove

| Artifact | Proves | Does not prove | SPEC audit use |
|---|---|---|---|
| **`SPEC.md`** | Declared product intent (goals, non-goals, architecture targets, roadmap narrative) | That code exists or tests pass | **Target text** of the audit; never silently overwritten by agents |
| **`docs/wiki/Goals.md`** | Strategic mission / “why we win” | API contracts or module inventory | Owner-vision context; Information Audit primary signal; not a substitute for SPEC engineering detail |
| **`AGENTS.md`** | Operating process, authority split, prohibited agent actions | Product feature presence | Bounds audit *actions* (no auto-write SPEC; human gates); process drift is separate from product SPEC drift |
| **`.agentic/releases/** fragments** | Named capability claimed shipped or staged, surfaces, links, migration notes | Full test coverage or user value | Primary **implementation evidence** for `aligned` / `undocumented` (#338) |
| **Filesystem path citations** | Cited path exists or is missing | Behavioral correctness | `stale_evidence` when SPEC cites missing paths |
| **`CURRENT.md`** | Human/agent-maintained verified reality summary | Exhaustive inventory | Secondary reality check; prefer fragments + tests for machine audit |
| **Tests / workflows** | Behavioral and gate evidence | Product desirability | Preferred stronger evidence in follow-ups (noted in #338 notes; design #337 should sequence) |
| **GitHub Issues / PRs** | Acceptance criteria, decision comments, merge history | Stable product contract | Provenance and follow-up routing (#339 issue creation); not SPEC prose authority |
| **Curiosity answers / Question artifacts** | Explicit owner answers with answer_signal | Full architecture | Preferred **owner-vision intake** channel when SPEC/Goals are silent or ambiguous |
| **Chat history** | Ephemeral discussion | Durable truth | Explicitly non-authoritative per AGENTS.md |

### 2. Precedence model for conflicts

Apply the **highest applicable tier**. Lower tiers may only *propose* changes upward via Documentation PRs / Questions—not overwrite.

```
Tier 0 — Safety & process locks (non-negotiable)
  AGENTS.md authority table + human Task rules
  risk:critical / need:human-review / credential & workflow paths
  Never auto-edit SPEC.md, AGENTS.md, CODEOWNERS, workflows, secrets

Tier 1 — Explicit owner vision (human judgment)
  Recent human-approved answer on a Question (curiosity / contemplation)
  Explicit human decision on Design/Research approval (#632) when scoped
  Human merge of Documentation PR that updates SPEC or Goals

Tier 2 — Product intent documents
  SPEC.md (engineering/product desired state)
  Goals.md (mission/strategy; resolve mission conflicts here first,
            then reflect engineering implications into SPEC)

Tier 3 — Verified / staged implementation evidence
  Versioned release fragments + tags (shipped)
  Unreleased fragments on release branch (staged for next cut)
  Tests / required CI workflows (behavioral)
  CURRENT.md (narrative reality; lower trust than fragments+tests)

Tier 4 — Planning & history
  Open Issues / Epics / milestones (intent of work, not shipped truth)
  Closed issue bodies and PR descriptions (historical)
  Design docs under docs/design/ (proposals until approved + reflected)

Tier 5 — Inference (lowest)
  Agent chat, heuristics, “seems missing from SPEC”
```

#### Conflict resolution recipes (examples for Design #337)

| Conflict | Prefer | Agent action |
|---|---|---|
| Fragment says feature shipped; SPEC silent | Tier 3 evidence → propose SPEC additive update | `undocumented` finding → Documentation PR / follow-up issue (#339); **do not** auto-write SPEC |
| SPEC cites path; file missing | Filesystem truth | `stale_evidence`; fix SPEC citation or restore artifact |
| SPEC describes future capability; no code | Tier 2 future intent | `future_ok` — **not an error** (planning #335/#338) |
| Goals mission vs SPEC engineering | Tier 1 human if unresolved; else Goals for mission, SPEC for product shape | Open Question if agents cannot reconcile |
| AGENTS process vs SPEC product narrative | Both may be correct in their domain | Process drift → AGENTS/process PR; product drift → SPEC PR |
| Book prose vs plate_core implementation | Repo implementation + corrective issue (AGENTS authority model) | Do not keep dual truths indefinitely |
| Chat “we decided X” vs no GitHub artifact | Tier 5 loses | Record Question answer or Documentation PR before treating as truth |
| CURRENT.md contradicts fragments | Prefer fragments + tests | Update CURRENT; optional SPEC if intent changed |

### 3. How owner vision should be captured (explicit intake)

**Recommendation:** multi-channel, with clear roles—avoid a fourth parallel “vision file” unless Goals+SPEC prove insufficient.

| Channel | Use when | Closure artifact |
|---|---|---|
| **`SPEC.md` Documentation PR** | Product scope, architecture, non-goals, beta/v1 roadmap narrative | PR + fragment if process/surface impact; human merge |
| **`docs/wiki/Goals.md`** | Mission, strategic success, principles | Wiki/docs PR; Information Audits read first |
| **Question + answer_signal** | Discrete decisions, ambiguities, “should we…?” | Contemplation + docs/research or SPEC/Goals update |
| **Design / Research approval (#632)** | Artifacts that need approve/revise/reject before becoming authoritative | `.agentic/approvals/` pointer + history |
| **Human Task** | Real-world / external identity (credentials, marketplace, billing) | `<!-- PLATE-TASK-CLOSED -->` — never agent-completed |

**Do not** treat agent-inferred “owner would want X” as Tier 1. Intake must leave a GitHub- or repo-durable marker.

Overlap with Information Audit (#218): Goals page gaps → Questions; SPEC audit gaps → Documentation/Bug/Question via #339 routing. Keep engines separate but share precedence language.

### 4. Mapping to shipped SPEC audit surface (#338–#340)

| Finding kind | Hierarchy meaning |
|---|---|
| `aligned` | Tier 3 fragment surface reflected in Tier 2 SPEC text |
| `undocumented` | Tier 3 evidence without Tier 2 text → propose additive SPEC (human gate) |
| `stale_evidence` | Tier 2 citation fails filesystem check |
| `future_ok` | Tier 2 without Tier 3 — allowed |
| `conflict` | Engine could not load evidence (operational), not product conflict |

Health (#340) exposes `spec_audit_status` / actionable next steps; `what_next` prioritizes actionable findings after open PRs and bootstrap—consistent with “finish pipeline, then reconcile intent.”

### 5. Design questions handed to #337

1. **Reconciliation states:** draft, proposed, human-approved, applied, deferred, future_ok—state machine and which artifacts may transition which edges.
2. **Placement rules:** where additive SPEC sections insert when confidence is medium/low (#341 cluster).
3. **Evidence upgrade path:** when tests/workflows become required evidence vs optional enrichment.
4. **Draft SPEC table UX:** issue comment vs PR-only; still never auto-apply (#339 human-approval gate).
5. **Goals vs SPEC dual-write:** when a vision answer updates both mission and engineering sections in one PR vs sequenced PRs.

## Recommendation

1. **Adopt the Tier 0–5 precedence table** as the SPEC auditing contract in Design #337; cite this research.
2. **Keep SPEC human-owned:** agents only propose (findings, follow-up issues, draft tables); human merge applies intent changes.
3. **Owner vision intake:** Goals (mission) + Questions (decisions) + SPEC Documentation PRs (product); no silent chat authority.
4. **v1 engine stays fragment + path focused** until #337 specifies tests/workflows as first-class evidence.
5. **Close #336** with this artifact; open/refresh #337 design to encode reconciliation states and placement rules.

## Non-goals of this research

- Changing audit engine scoring thresholds (implementation detail)
- Closing #337 (Design) or re-opening #335 Epic ceremony
- Claiming SPEC is fully aligned with all unreleased fragments (operational follow-up via `gh plate spec-audit`)

## Related issues

- Epic #335; Features #338, #339, #340 (shipped)
- Design #337 (next)
- Question #341 (low-confidence insertion routing; closed/related)
- Information Audit #218 / Goals #224
- Autonomy safety: #645 shadow, #648 checkpoint, #647 ledger (SPEC writes remain human-gated)
