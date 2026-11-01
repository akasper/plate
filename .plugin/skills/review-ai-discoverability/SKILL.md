---
name: Review AI Discoverability
description: Audit agent-readable surfaces and public claims so AI assistants and answer engines can read, verify, and cite the product honestly.
---

<!-- PLATE-GENERATED:BEGIN skills-surface -->
<!-- Do not edit generated skill surfaces manually. -->
<!-- Source of truth: src/plate_core/data/baseline_catalog.yml -->
<!-- Regenerate: python3 scripts/generate-plugin-skills.py -->

# Review AI Discoverability

> Skill id: `review-ai-discoverability`
> Generated from the baseline catalog. Regenerate with `python3 scripts/generate-plugin-skills.py`.

Audit agent-readable surfaces and public claims so AI assistants and answer engines can read, verify, and cite the product honestly.

**Owning agents:** dev-relations-expert, research-agent

## Inputs

- Public repo surfaces (README, AGENTS.md, docs, site, llms.txt when present)
- SPEC.md, CURRENT.md, and .agentic/marketing.yml claim policy
- Marketing or launch copy under review

## Outputs

- Completed checklist rows with evidence links
- Gap issues (surfaces and claims) with risk labels
- Summary of honest-tactics violations or escalations

## Examples

- Before launch, walk docs/marketing/ai-discoverability-review-checklist.md and file issues for untraceable README claims.

<!-- PLATE-GENERATED:END skills-surface -->

## When to run

- Before launch or major release when AI assistants, coding agents, or answer engines are an audience ([#1159](https://github.com/akasper/plate/issues/1159)).
- After large README, docs-site, or marketing copy changes (parallel to legal [#1118](https://github.com/akasper/plate/issues/1118) and style [#1120](https://github.com/akasper/plate/issues/1120) review stages).
- Lazy-load this skill for discoverability work only; do not preload during unrelated feature or bug loops.

## Checklist (required)

Read and complete `docs/marketing/ai-discoverability-review-checklist.md` (repo root; copied on bootstrap/import-payload). Work **surfaces** and **claims** sections separately; every row needs Status + Evidence or N/A with reason.

## Honest tactics (non-negotiable)

- Every public claim must trace to `SPEC.md` or a linked GitHub issue—never invent capabilities or endorsements.
- No hidden text, no prompt-injection aimed at models, no fake reviews or social proof.
- This skill is not legal advice; escalate legal, compliance, or store-policy gaps per Epic [#1118](https://github.com/akasper/plate/issues/1118) instead of improvising policy text.

## Procedure

1. **Scope** — list URLs/paths in review (README, docs tree, site root from `.agentic/marketing.yml`, optional `llms.txt`, GitHub About metadata).
2. **Surfaces pass** — for each checklist row, verify readability, working links, and parity with `CURRENT.md` / `SPEC.md`; note broken or agent-hostile structure.
3. **Claims pass** — for each marketing or README claim, locate `SPEC.md` or issue proof; flag untraceable, exaggerated, or prompt-injection content.
4. **File work** — open issues per gap with `risk:*` and `need:*` as appropriate; use `Task` when human-only approval is required (public claim changes, legal copy).
5. **Record** — attach the updated checklist (or audit note) to the PR, release checklist, or `docs/audits/` when dogfooding.

## Done gate

Checklist surfaces and claims tables are complete (no TBD rows without owner), honest-tactics checks pass or are escalated, and follow-up issues link back to the review scope.

