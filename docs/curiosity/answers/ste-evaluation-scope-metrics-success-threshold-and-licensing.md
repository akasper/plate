# Answers for Question #1087

**Title:** STE evaluation: scope, metrics, success threshold and licensing
**Issue:** #1087

This file is generated from committed Answer Model data. GitHub comments remain the source of truth.

**Latest effective answer:** 2026-10-31T12:50:02Z by akasper

## Answer 1

- **Answer id:** 6543576450
- **Answered by:** akasper
- **Timestamp:** 2026-10-31T12:50:02Z
- **Source:** Andrew via PM bot multiple-choice card 2026-10-31
- **Session:** pm-bot-mc-card-2026-10-31
- **GitHub comment:** https://github.com/akasper/plate/issues/1087#issuecomment-6543576450

```text
## Answers (Andrew, 2026-10-31)

**Q4 card: scope and deciding metric**
> Q: For the Simplified Technical English evaluation, what text is in scope and what metric decides?
> A (verbatim): PLATE #1087: scope AGENTS.md, skills and MCP tool descriptions; decide on input tokens per task with success rate as a guardrail

**Q5 card: test arms and adoption threshold**
> Q: Which test arms, and what saving is enough to adopt?
> A (verbatim): PLATE #1087: STE-lite only, adopt at 15%+ fewer input tokens with no drop in success rate

**Mapped to the questions in this issue**
1. **Scope:** AGENTS.md, skills, and MCP tool descriptions. Out of scope for v1: CLI `--help`, issue/PR templates, wiki, agent output.
2. **Metrics:** input tokens per task decides; task success rate is a guardrail.
3. **Threshold:** adopt at 15% or more fewer input tokens per task with no drop in success rate.
4. **Models:** not asked on this card; default stays the included coding model at standard speed (per cost rules).
5. **Arms:** STE-lite only (the style prompt in #1086). No strict-STE arm.
6. **Licensing:** the ASD-STE100 terms-of-use check still happens regardless, before anything from the spec or dictionary goes into the repo or a linter.

Recorded in the Epic body (#1086). `need:decision` removed. This Question still needs its `Closes #1087` research PR (`docs/research/`), which has not been opened.

**Provenance / session notes**
Andrew picked these on a multiple-choice card that the PM bot showed him in chat on 2026-10-31. The PM bot recorded them here.
```
