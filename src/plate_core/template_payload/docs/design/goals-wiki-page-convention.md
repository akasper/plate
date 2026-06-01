# PLATE Convention: Goals Wiki Page

**Status:** Adopted (Epic #218 / Feature #224)

## Purpose

Every PLATE project should maintain a `Goals` page in its GitHub Wiki. This page serves as the canonical, agent-accessible source for the project's high-level **strategic mission and guiding principles** — *why* the project exists and *how* it intends to succeed.

This is intentionally distinct from `SPEC.md`, which focuses on product implementation details, architecture, engineering outcomes, and process rules.

## Why This Convention Exists

- Gives agents a clear, durable view of strategic intent during Information Audits.
- Separates "mission / go-to-market / success model" thinking from day-to-day implementation planning.
- Creates a natural home for long-lived Informational Goals that cut across many Epics and Features.
- Supports the broader goal of making Q&A with agents the primary development workflow.

## Recommended Location and Structure

**Primary location (after wiki sync):** The project's GitHub Wiki, as a top-level page named `Goals`.

**Source of truth (in repo):** `docs/wiki/Goals.md` (recommended). This allows the page to participate in normal PLATE documentation workflows and wiki sync when enabled.

### Suggested Structure (lightweight)

```markdown
# Goals

[Short 1-2 paragraph introduction explaining the page's purpose for humans and agents]

## Mission

[1-4 broad directional statements describing why the project exists and how it will succeed. Include go-to-market, revenue model, target impact, deployment philosophy, etc. as appropriate.]

## Core Principles

- Principle 1 (with short rationale)
- Principle 2 (with short rationale)
...

## How We Intend to Succeed

- Broad strategic outcome 1
- Broad strategic outcome 2
...

## Current State & Evidence

[Light, high-level snapshot. Not a detailed roadmap.]

## Open Strategic Questions

[Links to relevant `Question` issues that represent major unresolved informational goals against the mission above.]
```

Keep the structure mostly prose. Heavy machine-readable sections are not required at this time.

## Relationship to Other Artifacts

- **SPEC.md**: Implementation vision, users/personas (detailed), architecture, non-goals, constraints. SPEC.md may continue to have its own lighter `## Goals` section focused on engineering outcomes.
- **AGENTS.md**: Process rules and authority model.
- **Question issues**: Track specific informational gaps against the Goals on this page.
- **`.agentic/releases/`**: Track what has actually been delivered toward the mission.

## Adoption Guidance (for new and existing projects)

- New projects: Bootstrap should offer to initialize a basic `Goals` page (with placeholders) when wiki sync is enabled or when the user indicates interest in strategic/agentic planning.
- Existing projects: Migration involves creating the page (manually or via a helper) and linking it from the wiki Home and relevant documentation.
- Agents should be able to detect the presence/absence of a `Goals` page and surface it as a high-value informational goal when missing.

## Agent Expectations

Agents performing Information Audits are expected to:
- Read the `Goals` page as one of the primary strategic signals.
- Generate or refine `Question` issues for gaps between current state and the mission/principles described.
- Propose updates to the `Goals` page itself when they discover important strategic shifts (via human-approved Documentation PRs).

## Open Questions (for this convention)

- Should there be a lightweight machine-readable section (e.g., a small YAML block) for certain fields in the future?
- How strictly should we enforce the presence of this page via health checks or audits?
- What is the right balance between "broad mission" on this page vs. more concrete outcomes on dedicated strategy or roadmap wiki pages?

---

*This document defines the recommended PLATE convention. Refined and adopted as part of Epic #218.*