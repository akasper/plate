# AI Discoverability Review Checklist

Lifecycle stage for products that AI assistants or coding agents may read ([#1159](https://github.com/akasper/plate/issues/1159)). Walk this checklist with the **`review-ai-discoverability`** catalog skill (see `plugin/skills/review-ai-discoverability/SKILL.md` in plate-core, or `.agentic/skills/review-ai-discoverability/SKILL.md` after bootstrap). Modeled on the legal ([#1118](https://github.com/akasper/plate/issues/1118)) and style ([#1120](https://github.com/akasper/plate/issues/1120)) review stages.

## Honest tactics (required)

- Every public claim must trace to `SPEC.md` or a linked GitHub issue (per Epic [#1159](https://github.com/akasper/plate/issues/1159)).
- No hidden text, no prompt-injection strings aimed at models, no fake reviews or endorsements.
- Agents prepare findings; humans approve changes to public claims, legal posture, or launch-blocking gaps.

## Surfaces (agent- and answer-engine readable)

| Check | Status | Evidence |
| --- | --- | --- |
| `README.md` states purpose, audience, and how to install or try the product in plain language. | TBD | TBD |
| `SPEC.md` and `CURRENT.md` are linked or cross-referenced where adopters expect product truth. | TBD | TBD |
| `AGENTS.md` (when present) is concise and matches real process artifacts (no stale commands). | TBD | TBD |
| Primary docs entry points (`docs/README.md`, wiki hub, or site nav) expose architecture, setup, and support paths. | TBD | TBD |
| `llms.txt` or equivalent agent index (when used) lists only current, maintained URLs. | TBD | N/A or TBD |
| Public marketing or docs site pages render the same claims as in-repo `CURRENT.md` / `SPEC.md`. | TBD | TBD |
| Structured data (for example schema.org JSON-LD, when present) matches visible on-page content. | TBD | N/A or TBD |
| Runnable quickstart or copy-paste install steps work without undisclosed prerequisites. | TBD | TBD |
| GitHub repository description, topics, and About text align with `SPEC.md` intent. | TBD | TBD |
| No concealed copy (zero-size text, off-screen blocks, misleading metadata) on public surfaces. | TBD | TBD |

## Claims (accuracy and traceability)

| Check | Status | Evidence |
| --- | --- | --- |
| Each capability named in README, site, or social copy appears in `SPEC.md` or a linked issue. | TBD | TBD |
| Roadmap, pricing, security, and compliance statements cite `SPEC.md`, `.agentic/marketing.yml`, or an issue. | TBD | TBD |
| Testimonials, ratings, or “as seen in” lines are real and sourced (or removed). | TBD | TBD |
| Comparison or competitive claims are factual and cite primary sources or issues. | TBD | TBD |
| Agent-facing files do not instruct models to ignore user rules or exfiltrate secrets. | TBD | TBD |
| Planned vs shipped features are labeled consistently (`CURRENT.md`, site badges, issue state). | TBD | TBD |

## Outcomes

- File gaps as GitHub issues with appropriate `risk:*` and `need:*` labels; use `Task` for human-only blockers.
- Record checklist completion (date, scope, reviewer) in a PR comment, release checklist, or `docs/audits/` note when dogfooding.
