# OpenSpec Evaluation for PLATE

- **Issue:** #35
- **Researched by:** @copilot (agent session)
- **Date:** 2026-05-26
- **Status:** Completed

## Research Question

Can PLATE use OpenSpec by default? If so, where does it fit relative to PLATE's existing `SPEC.md`, `CURRENT.md`, issue workflow, and documentation responsibilities?

## Sources

- [OpenSpec](https://openspec.dev/)
- [OpenSpec — thedocs.io](https://thedocs.io/openspec/)
- [What is OpenAPI? — OpenAPI Initiative](https://www.openapis.org/what-is-openapi)
- [AsyncAPI document structure](https://www.asyncapi.com/docs/concepts/asyncapi-document/structure)
- Existing PLATE artifacts: `AGENTS.md`, `SPEC.md`, `CURRENT.md`, `.agentic/process.yml`

## Findings

### What OpenSpec is

OpenSpec is a lightweight, repository-native spec-driven development workflow aimed at human + AI collaboration. Its core idea is to make proposed changes explicit before implementation, with durable Markdown artifacts instead of transient chat context. The framework emphasizes:

- **proposed changes before code**
- **repo-owned specs as the source of truth**
- **brownfield adoption** for existing codebases
- **AI-friendly structured context** that survives beyond a single session

That aligns well with PLATE's general philosophy of durable artifacts and traceability.

### What problem OpenSpec solves

OpenSpec is strongest when a team needs to describe a **specific upcoming change** in a structured way before coding. It helps answer:

- What requirement is changing?
- What scenarios define the expected behavior?
- What implementation tasks flow from that change?
- What documentation should be archived once the change lands?

This is complementary to PLATE, but not identical. PLATE already splits truth across:

- `SPEC.md` for intended future-state product definition
- `CURRENT.md` for implemented behavior and evidence
- issues / PRs / docs for traceable work execution

OpenSpec would add a more formal **change-spec layer** between intent and implementation.

### Comparison with OpenAPI and AsyncAPI

| Tool | Primary purpose | Best fit in PLATE |
|---|---|---|
| **OpenSpec** | Change-oriented product / system specification workflow in Markdown | Planning and reviewing non-trivial feature changes before implementation |
| **OpenAPI** | Contract for HTTP APIs in YAML/JSON | REST API interface definition, client generation, testing, infra configuration |
| **AsyncAPI** | Contract for event-driven / messaging APIs | Message brokers, channels, events, async integration design |

OpenSpec is **not** a replacement for OpenAPI or AsyncAPI. The official OpenAPI and AsyncAPI materials are contract-focused and describe interface structure for concrete HTTP or event-driven APIs. OpenSpec is broader and earlier in the lifecycle: it describes the intended change, not the machine-readable runtime interface.

Practical implication for PLATE:

- Use **OpenAPI** when a PLATE project exposes HTTP APIs.
- Use **AsyncAPI** when a PLATE project exposes event-driven contracts.
- Consider **OpenSpec** when a PLATE project needs stronger pre-implementation change design, especially with AI-heavy workflows.

### Fit with PLATE's existing model

OpenSpec maps best to a new optional layer:

| PLATE artifact | Role today | OpenSpec relationship |
|---|---|---|
| `SPEC.md` | Product-level future state | Remains the high-level product specification |
| `CURRENT.md` | Implemented truth + evidence | Remains the post-implementation record |
| Issues / PRs | Task routing and traceability | Remain the execution and review mechanism |
| **OpenSpec change docs** | Not present today | Could describe substantial proposed changes before implementation |

This means OpenSpec fits PLATE as a **supplement**, not a replacement.

### Benefits if PLATE adopts OpenSpec

1. **Better pre-code review for agents.** It gives agents a stable requirement artifact before they start implementing.
2. **Improved brownfield change planning.** Downstream PLATE repositories may need a lightweight way to plan changes without rewriting `SPEC.md` for every feature.
3. **Cleaner archival of design intent.** OpenSpec's propose → implement → archive lifecycle fits PLATE's evidence-first posture.
4. **Potential bridge to API contracts.** A change spec could reference resulting OpenAPI or AsyncAPI artifacts when the feature is interface-heavy.

### Risks or drawbacks

1. **Process overlap.** PLATE already has `SPEC.md`, `CURRENT.md`, issue templates, research docs, and design docs. Adding OpenSpec by default would create another required artifact family.
2. **Template bloat.** The base template is meant to be lightweight. Scaffolding OpenSpec directories and conventions into every new repo would raise cognitive load before teams know they need it.
3. **Unclear governance boundary.** PLATE currently uses issue types and docs directories to express research/design work. OpenSpec introduces a parallel vocabulary that would need explicit mapping.
4. **Not machine-contract specific.** PLATE still needs OpenAPI / AsyncAPI for actual interface contracts. OpenSpec does not remove that need.

## Recommendation

### Recommendation: **Do not make OpenSpec a mandatory default in the base PLATE template yet.**

Instead, treat it as a **recommended optional companion** for downstream PLATE repositories that have one or more of these traits:

- complex multi-step feature design
- heavy AI-assisted implementation
- brownfield systems where change intent is easy to lose
- teams that want reviewable change specs before opening implementation PRs

### Proposed PLATE posture

1. Keep `SPEC.md` and `CURRENT.md` as the canonical PLATE top-level artifacts.
2. Preserve OpenAPI / AsyncAPI as the interface-contract tools when a project needs them.
3. Add OpenSpec later as either:
   - a documented optional workflow in PLATE docs, or
   - an installable PLATE extension for change-spec scaffolding.
4. Only consider making it default after PLATE defines a precise mapping from OpenSpec change docs to issues, `CURRENT.md`, and release evidence.

### SPEC.md impact

No `SPEC.md` update is recommended in this PR.

Reason: the research does **not** support making OpenSpec part of PLATE's default required state today. Adding it to the template's canonical spec now would overstate adoption and create process ambiguity.

## Recommendation Summary

| Question | Answer |
|---|---|
| Is OpenSpec a good conceptual fit for PLATE? | **Yes, as a complement** |
| Does it replace OpenAPI / AsyncAPI? | **No** |
| Should PLATE adopt it by default right now? | **No** |
| Best next step | Offer it later as optional guidance or an extension |

Closes #35
