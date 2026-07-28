# Goals

**Authority (hybrid model, post–v0.8.0 / #991):** This page is the short **single source of truth for PLATE’s product mission and success metrics**. Information Audits and agent planning should treat Mission / Principles / How We Intend to Succeed / Current State as **committed project claims**, not template placeholders.

Depth that does not fit here may live in `SPEC.md` (implementation), release notes under `.agentic/releases/`, and research under `docs/research/`. A **clearly marked adopter convention** section at the bottom preserves the Goals page pattern for new PLATE projects.

---

## Mission

PLATE (Process Lifecycle Agentic Task Engine) exists to make **reliable, high-velocity agentic software development the default** way teams build on GitHub.

We build the operating system for agent-driven development: conventions, tools, and runtime surfaces (`plate-core`, `gh plate`, `plate-mcp`, CLI agent plugins) that let AI agents own the majority of the software development lifecycle while **humans keep judgment** on risk, architecture, product direction, and irreversible external actions. **GitHub preserves truth** — Issues, PRs, labels, milestones, release fragments, and wiki source are the durable project memory.

## Core Principles

- **GitHub is the Single Source of Truth** — Planning, execution state, answers, and release evidence live in GitHub-native and repo-committed artifacts, not chat history.
- **Agent autonomy is the default; humans keep judgment** — Agents drive toil and process loops; humans decide scope, merge risk, credentials, and public claims.
- **Test-first and evidence over assertion** — Progress is verifiable (tests, fragments, timed proofs, PR citations). Sketches and first slices are not “done” without E2E evidence.
- **Thin surfaces, quiet operations** — Prefer small, inspectable CLI/MCP tools and terse agent output over chatty ceremony or heavy hosts.
- **Lightweight and GitHub-native** — Process should feel native and add minimal friction; do not invent parallel planning systems.
- **Evolvable and adoptable** — Scale from solo developers to larger teams; new repos should reach meaningful agentic leverage quickly (adopter time-to-value).
- **Reversible by default** — Atomic PRs, easy squash/revert, explicit human checkpoints for high-risk paths.

## How We Intend to Succeed

Strategic outcomes for **this** product (PLATE / `plate-core`):

| Outcome | What “winning” looks like |
|---|---|
| **Adopter time-to-value** | A developer can adopt PLATE on an existing GitHub repo in **under 30 minutes** and immediately gain meaningful agentic leverage (health, what-next, adopt/import-payload, first Q&A or ready work). Near-term must-ship theme for #983 (see `docs/research/post-0.8.0-next-release-priorities.md`). |
| **Agent effectiveness** | Agents reliably drive day-to-day Feature/Bug/Docs loops, PR green/babysit, release ceremony helpers, and budgeted autonomy without inventing parallel process. |
| **Durability of knowledge** | Answers to informational goals (Q&A, research notes, Goals updates) remain discoverable and actionable over multi-day/multi-agent runs. |
| **Distribution reach** | Install path is real and documented: PyPI `plate-core`, `gh-plate` extension, MCP, and plugin marketplace install — without false drift or pin confusion. |
| **Ecosystem health** | PLATE remains a foundational layer that templates, extensions, and host agents can build on without forking process truth. |
| **Honest v1.0** | v1.0.0 (#654) is claimed only when autonomy-surface checklists are E2E-proven with tests and citations — not when sketches land. Intermediate 0.9.x cuts are expected. |

## Current State & Evidence

*(Snapshot after v0.8.0 — update at major cuts and when North Star shifts.)*

**Shipped foundations (v0.8.0):**

- Public **PyPI** package `plate-core==0.8.0`, shared library for CLI / MCP / plugins.
- **`gh plate`** thin-shim extension path and release-track / ceremony tooling.
- Autonomy and adoption foundations: budgeted AutonomyEngine, adopt / import-payload / self-migrate surfaces, quiet ops, baseline persona when PLATE signals are present.
- Endless feed / Q&A / planning primitives and Information Audit Goals convention (Epic #218 lineage).

**Active product bet (Next Release #983):**

- Primary theme: **adopter time-to-value** (under-30m path polish) — not PM/fleet expansion or marketplace as product theme.
- Marketplace publication (#380 / #381) is a **parallel human Task** track; does not block #983.
- Goals hybrid rewrite: this page (#993, decision #991).

**Not yet won (do not overclaim):**

- Live under-30m proof on a third-party repo remains a human-gated E2E residual.
- #654 v1.0.0 checklist items stay Partial until E2E evidence lands; do not check boxes from sketches alone.

Evidence pointers: `README.md`, `SPEC.md`, `docs/research/post-0.8.0-next-release-priorities.md`, `docs/wiki/V1-Autonomy-Surfaces-Epic-Closeouts.md`, `.agentic/releases/`.

## Open Strategic Questions

Track major unresolved mission-level gaps as `Question` issues (and research notes). Agents running Information Audits should read this page first, then open or refine Questions for gaps.

**Current themes (not exhaustive):**

- How do we make the under-30m adopt path **LIVE-proven** (not just locally dry-run) without weakening safety gates?
- When does autonomy reliability become the primary cut theme *after* adopter path is crisp?
- What install-friction evidence would promote marketplace Tasks from parallel-human to release-blocking?

---

## Adopter / template convention (for new PLATE projects)

> **This section is convention guidance for repositories that adopt PLATE.**  
> It is **not** PLATE’s own mission text. Downstream projects should keep Mission / Principles / Success **above** as *their* claims, and may copy or adapt the structure below.

Every PLATE project is encouraged to maintain a `Goals` page (`docs/wiki/Goals.md` and/or wiki sync) as the agent-accessible source for **why the project exists** and **how it intends to succeed**. This is distinct from `SPEC.md`, which holds product implementation details and engineering outcomes.

### Purpose of the Goals page (convention)

The page should answer:

- Why is this project being built?
- Who is it for, and what outcomes matter most?
- What does “winning” look like at a strategic level?
- What principles should guide major decisions?

Agents performing Information Audits are expected to read Goals as a primary strategic signal when identifying informational gaps.

### Recommended section map (convention)

| Section | Role |
|---|---|
| **Mission** | Broad directional statement (project-specific claims, not examples). |
| **Core Principles** | Stable constraints that route product and process decisions. |
| **How We Intend to Succeed** | Strategic outcomes / success metrics. |
| **Current State & Evidence** | Short snapshot + links to proof (releases, research, PRs). |
| **Open Strategic Questions** | Pointers to live `Question` issues, not a second backlog. |

Bootstrap and template payloads may seed a starter Goals page; replace examples with real claims as soon as product intent is known. Prefer Documentation PRs for updates so Git history remains the audit trail.

**PLATE Convention Note:** Goals is a primary input for the Information Audit system (Epic #218 lineage). Adopters who enable wiki sync may scope `docs/wiki/Goals.md` as a default synced page when present.
