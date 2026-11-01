# AI Discoverability Brief

Use this brief when your product may be described by AI assistants, coding agents, or answer engines—not only by humans on a marketing site. The goal is accurate, checkable representation of what the product actually does, grounded in repository truth.

| Field | Value |
|---|---|
| Product name | TBD |
| Primary agent-facing surfaces | TBD (for example public docs, `llms.txt`, schema.org JSON-LD, runnable quickstart) |
| Public URL | TBD |
| Owner | TBD |
| Review cadence | Baseline at launch; periodic re-check per `.agentic/marketing.yml` when configured |

## Audience

| Audience | What they need | Success signal |
|---|---|---|
| Prospective users asking an AI for recommendations | Factual description of capabilities and limits | Answers match `SPEC.md`, `CURRENT.md`, or linked issues |
| Coding agents evaluating install or integration | Correct commands, entry points, and constraints | Agent can follow documented quickstart without hallucinated APIs |
| Answer engines summarizing the product | Claims tied to evidence, not generic marketing copy | Control prompts in `prompt-set.md` pass at baseline |

## Claim and evidence policy

Follow the same honesty bar as other PLATE marketing artifacts (see Epic #1159 and #1111):

- Every factual claim must trace to `SPEC.md`, an open or closed GitHub issue, `CURRENT.md`, or another named repository artifact.
- Label planned or aspirational statements explicitly; do not present roadmap intent as shipped capability.
- Do not add hidden text, prompt-injection strings aimed at models, or fabricated reviews or endorsements.

When a public-facing sentence disagrees with `SPEC.md` or an issue, treat the repository artifact as authoritative and fix the surface or file a Bug.

## Surfaces in scope for this stage

Record which surfaces you maintain for agents and engines. Later lifecycle work may add automation; this template only tracks ownership and evidence.

| Surface | Location | Owner | Last reviewed |
|---|---|---|---|
| Product specification | `SPEC.md` | TBD | TBD |
| Implemented capability summary | `CURRENT.md` | TBD | TBD |
| Agent-oriented site index | TBD (`llms.txt` or equivalent) | TBD | TBD |
| Structured metadata | TBD (JSON-LD or similar) | TBD | TBD |
| Runnable quickstart | TBD | TBD | TBD |

## Open questions

List decisions that need human approval before expanding public or agent-facing claims (pricing, security posture, legal, roadmap dates).
