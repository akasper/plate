---
title: Design: SPEC audit workflow, reconciliation states, and human-approval boundaries
issue: 337
epic: 335
research: 336
status: accepted-for-v1
---

# Design: SPEC audit workflow, reconciliation states, and human-approval boundaries

- **Issue:** #337 (Design child of Epic #335 “SPEC auditing”)
- **Research:** #336 (`docs/research/336-spec-audit-source-of-truth-hierarchy.md`)
- **Shipped slices:** #338 engine, #339 follow-ups, #340 health/what_next
- **Date:** 2026-07-26
- **Status:** Accepted for v1 contract (documents shipped behavior + forward edges)

## Design goal

Define a concrete, implementation-ready contract for how SPEC auditing turns repository evidence into structured findings and corrective work while preserving **SPEC.md as human-owned and agent-assisted** (never silent agent overwrite).

This design adopts Research #336 Tier 0–5 precedence and freezes v1 CLI/MCP behavior already landed in #338–#340, plus the additive-first planning decisions from Epic #335.

## Non-goals

- Auto-applying SPEC.md patches without human merge
- Full rewrite / deletion of SPEC sections without explicit human guidance
- Replacing Information Audit (#218) or Goals intake (separate engine; shared precedence language only)
- Marketplace / external publish Tasks
- Claiming v1.0.0 readiness from sketches alone

---

## 1. Inputs

| Input | Required | Source | Notes |
|---|---|---|---|
| `repo_root` | yes (default `.`) | local checkout | Whole-repository fresh run (v1) |
| `SPEC.md` | yes for success | Tier 2 intent | Target document of the audit |
| Unreleased (+ collected) fragments | yes for evidence | `.agentic/releases/` | Tier 3 staged/shipped claims |
| Path citations in SPEC | derived | SPEC backticks / paths | For `stale_evidence` |
| Optional: `releases_dir`, `spec_path` | no | CLI/MCP flags | Testability / monorepo layout |

**v1 evidence scope:** fragments + filesystem path probes only.  
**Forward (post-v1 edge):** tests + required workflows may become first-class evidence when confidence thresholds are raised (see §6).

**Not inputs for product truth:** chat history, ephemeral agent memory (Tier 5).

---

## 2. Outputs

### 2.1 Structured audit report (primary)

Emitted as CLI/MCP JSON or markdown (`gh plate spec-audit`, `plate_spec_audit`):

```text
SpecAuditReport {
  ok: bool
  repo_root, spec_path: string
  counts: { aligned, undocumented, stale_evidence, future_ok, conflict }
  findings: SpecFinding[]
  notes: string[]
  error?: string
}

SpecFinding {
  kind: aligned | undocumented | stale_evidence | future_ok | conflict
  title: string
  confidence: high | medium | low
  evidence: string[]
  section?: string          # best-fit SPEC section when known
  recommendation: string
  metadata: object          # slug, path, links, placement notes
}
```

### 2.2 Follow-up plan / apply (#339)

- **Plan (dry-run):** proposed GitHub issues with type labels + dedupe markers  
  `<!-- PLATE-SPEC-AUDIT-FOLLOWUP:… -->`
- **Apply:** create issues only when requested (`--apply-followups` / MCP apply)
- **Additive SPEC draft table:** markdown table of proposed insertions posted as issue/PR **comment** — never written to SPEC.md by the engine

### 2.3 Health / orchestration surfaces (#340)

| Field | Meaning |
|---|---|
| `spec_audit_status` | `ok` \| `actionable` \| `advisory` \| `missing` \| `error` \| `skipped` |
| `spec_audit_counts` | finding counts |
| `spec_audit_actionable_count` | undocumented + stale_evidence + conflict |
| `spec_audit_next_step` | one-line operator/agent next action |

`plate_what_next` priority: budget → open PRs → bootstrap → **actionable SPEC audit** → ready issues → epics.

---

## 3. Core finding categories (reconciliation states)

Finding **kinds** are the stable reconciliation vocabulary. Map Research #336 hierarchy meaning:

| Kind (state) | Meaning | Actionable? | Default route (#339) |
|---|---|---|---|
| `aligned` | Tier 3 fragment surface reflected in SPEC | no | none |
| `undocumented` | Implemented/staged evidence not in SPEC | **yes** | Documentation |
| `stale_evidence` | SPEC cites missing path / broken evidence | **yes** | Bug |
| `future_ok` | SPEC intent without implementation | no (allowed) | none |
| `conflict` | Engine/evidence load failure or operational conflict | **yes** | Question |
| *(derived)* `ambiguous_vision` | Multiple equally good insertion points or Goals↔SPEC mission clash | soft | Question (when surfaced) |

**Derived presentation states** (health, not separate finding kinds):

| Health status | Condition |
|---|---|
| `actionable` | actionable_count > 0 |
| `advisory` | only `future_ok` without aligned evidence (review, not error) |
| `ok` | no actionable findings |
| `missing` / `error` / `skipped` | SPEC absent, audit failed, or audit disabled |

### 3.1 Reconciliation lifecycle (finding → landed intent)

```text
  [fresh audit run]
        │
        ▼
   finding emitted ──► plan follow-ups (optional)
        │                      │
        │                      ▼
        │              proposed issue (open)
        │                      │
        │         ┌────────────┼────────────┐
        │         ▼            ▼            ▼
        │     Documentation  Bug        Question
        │     PR draft       fix PR     answer_signal
        │         │            │            │
        │         └────────────┼────────────┘
        │                      ▼
        │              human review / merge
        │                      │
        │                      ▼
        │              applied (SPEC/Goals/code)
        │                      │
        └──────────────────────► re-audit → aligned | deferred
```

| Lifecycle edge | Who may act | Artifact |
|---|---|---|
| emit finding | agent / CLI | report JSON/markdown |
| propose follow-up | agent with apply flag | GitHub issue + marker |
| draft SPEC insertion table | agent | comment only |
| **land SPEC change** | **human merge** of Documentation PR | SPEC.md diff |
| land code/path fix | agent Feature/Bug PR (normal gates) | code + tests |
| resolve vision ambiguity | human Question answer | curiosity/SPEC/Goals update |
| defer | human labels issue deferred / closes wontfix | issue state |

**Deferred:** open follow-up closed without SPEC change; next audit may re-emit if evidence still drifts (dedupe markers prevent spam when issue remains open).

---

## 4. When to open which follow-up work

| Signal | Open | Do not open |
|---|---|---|
| `undocumented` high/medium, clear surface | **Documentation** issue → Documentation PR additive SPEC | Feature (capability already evidenced) |
| `undocumented` but product intent unclear | **Question** (owner vision) | Speculative SPEC rewrite |
| `stale_evidence` path should exist | **Bug** (restore artifact or fix citation) | Documentation-only if path is intentional removal → then Documentation to drop citation |
| `conflict` / load failure | **Question** or ops Bug | Silent ignore |
| Multiple insertion points / low confidence placement | **Question** or low-confidence note on Documentation issue | Auto-pick without noting ambiguity |
| Goals mission gap (not SPEC engineering) | Information Audit → **Question** (#218) | SPEC audit Documentation for mission prose |
| Process/AGENTS drift | process Documentation / Feature under process epics | SPEC product section |
| External account / credentials | **Task** (human-only) | Agent “fix” |

**Research / Design:** open when audit reveals missing *contract* (e.g. new evidence class), not for routine undocumented fragments.

**Feature:** only if audit shows SPEC promises a capability that is *not* evidenced and product wants it built — that is product planning (#628/#630), not default audit routing.

---

## 5. Human approval boundaries

| Action | Agent may | Human must |
|---|---|---|
| Run audit (CLI/MCP/health) | yes | — |
| Emit findings / draft SPEC table comment | yes | — |
| Create follow-up issues (apply) | yes (explicit apply) | review/prioritize |
| Open Documentation PR with SPEC additive text | yes | **merge approval** |
| Edit SPEC.md on `main`/`release` directly | no | merge PR |
| Rewrite/delete existing SPEC sections | no (v1) | explicit guidance + PR |
| Change AGENTS.md / workflows / secrets with audit | no | separate human process |
| Auto-merge Documentation PR when risk-off | no | human merge |
| Shadow/checkpoint high-impact (#645/#648) | when configured | approve when gates require |

**Additive and insertion-first (Epic #335):**

1. Prefer new bullets/subsections over rewriting paragraphs.
2. Per-finding confidence `high|medium|low` on each insertion.
3. If no obvious section: may propose **new SPEC section** with title + rationale.
4. If multiple sections fit: choose one best-fit, set confidence ≤ medium, record ambiguity in `metadata` / follow-up Question.
5. Single combined draft SPEC patch (table or unified markdown) per audit run for human review — not many silent micro-edits.

---

## 6. Placement rules (insertions)

| Case | Rule |
|---|---|
| Surface matches existing section keywords | Insert under that `##` / `###` |
| Architecture/runtime surface | Prefer Architecture / Core Components / Goals-adjacent technical sections |
| Process-only fragment | Prefer process docs/AGENTS — not SPEC product intent (or mark out-of-scope) |
| Confidence low | Still propose insertion + open Question if owner vision needed |
| Deletion of SPEC text | Out of v1 auto-draft; human PR only with guidance |

---

## 7. Evidence upgrade path (forward)

| Phase | Evidence | Required for `undocumented`? |
|---|---|---|
| **v1 (now)** | unreleased/versioned fragments + path citations | fragment change_type in feature/process/breaking/fix |
| **v1.1** | + unit/e2e test path presence | optional boost to high confidence |
| **v1.2** | + required workflow job names | optional; never sole evidence for product intent |

Tests/workflows **enrich confidence**; they do not replace human SPEC ownership.

---

## 8. Surfaces contract (implementation-ready)

| Surface | Behavior |
|---|---|
| `gh plate spec-audit` | Fresh whole-repo report; `--json`; `--followups` / `--apply-followups` |
| `plate_spec_audit` / `plate_spec_audit_followups` | MCP parity |
| `gh plate health` / `plate_health` | Additive `spec_audit_*` fields; `--repo-root`; `--no-spec-audit` |
| `plate_what_next` | Prioritize `actionable` after pipeline/bootstrap |
| Draft SPEC table | Comment or PR body section only |
| Ledger / checkpoint | Optional record of apply-followups and human decisions (#647/#648) — recommend markers already used |

---

## 9. Representative scenarios

### S1 — Fragment shipped, SPEC silent
- **Inputs:** fragment `foo-bar` surface `src/plate_core/foo.py`; SPEC lacks tokens  
- **Finding:** `undocumented` confidence medium  
- **Route:** Documentation issue → additive SPEC PR  
- **Outcome after human merge + re-audit:** `aligned`

### S2 — SPEC cites missing path
- **Inputs:** SPEC `` `src/old/path.py` `` missing on disk  
- **Finding:** `stale_evidence`  
- **Route:** Bug (restore) or Documentation (drop citation)  
- **Human chooses** based on product intent

### S3 — Future roadmap in SPEC, no code
- **Finding:** `future_ok`  
- **Health:** may be `advisory` if no aligned evidence  
- **Route:** none required; not an error

### S4 — Ambiguous section placement
- **Finding:** `undocumented` + metadata.ambiguity  
- **Route:** Documentation with low confidence **or** Question  
- **Must not:** rewrite three sections to force fit

### S5 — Goals mission vs SPEC engineering clash
- **Not pure SPEC audit:** Information Audit + Question (Tier 1)  
- **Then:** human-guided SPEC and/or Goals Documentation PRs

### S6 — Pipeline busy
- **what_next:** open PR babysit before SPEC drift  
- **Rationale:** land code evidence before reconciling intent

---

## 10. Relation to authority model

- **Tier 0:** AGENTS process locks, human Tasks, high-risk paths  
- **Tier 1:** human-approved Questions / Design-Research approvals / merged Doc PRs  
- **Tier 2:** SPEC.md + Goals.md  
- **Tier 3:** fragments, tests, CURRENT.md  
- **Tier 4–5:** issues/history/chat — proposals only  

See Research #336 for full tables.

---

## 11. Implementation status vs this design

| Design element | Status |
|---|---|
| Finding kinds + report | **Shipped** #338 |
| Follow-up routing + draft table | **Shipped** #339 |
| Health + what_next | **Shipped** #340 |
| Precedence research | **Shipped** #336 |
| This workflow/states contract | **This document** #337 |
| Tests/workflows as first-class evidence | Forward (v1.1+) |
| Full reconciliation state machine persistence | Optional; GitHub issues + re-audit sufficient for v1 |

---

## 12. Acceptance criteria traceability

| AC | Where satisfied |
|---|---|
| Inputs, outputs, finding categories | §1–§3 |
| Reconciliation states | §3, §3.1 |
| When to open Question/Research/Design/Feature/Bug/Documentation | §4 |
| Human approval boundaries draft vs land | §5 |
| Committed under `docs/design/` citing #335/#336 | this file |

## Related

- Epic #335; Research #336; Features #338, #339, #340  
- Information Audit #218; Goals #224  
- Autonomy safety #645, #648, #647 (SPEC writes remain human-gated)
