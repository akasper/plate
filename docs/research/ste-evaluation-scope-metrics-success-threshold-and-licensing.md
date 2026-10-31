# STE evaluation: scope, metrics, success threshold and licensing

- **Question:** [#1087](https://github.com/akasper/plate/issues/1087)
- **Status:** Answered
- **Answered by:** @akasper, 2026-10-31
- **Source of truth:** https://github.com/akasper/plate/issues/1087#issuecomment-6543576450
- **Answer format on the issue:** plate-answer-provenance
- **Committed mirror:** `docs/curiosity/answers/ste-evaluation-scope-metrics-success-threshold-and-licensing.md`, `docs/curiosity/answers.yml`

## Decision

Andrew decided (2026-10-31) the STE evaluation scope and success rule. In scope: AGENTS.md, skills, and MCP tool descriptions (CLI --help, issue/PR templates, wiki and agent output are out of scope for v1). Input tokens per task is the deciding metric, with task success rate as a guardrail. The only test arm is STE-lite (the style prompt in Epic #1086), with no strict-STE arm. Adopt when STE-lite cuts input tokens per task by 15% or more with no drop in success rate. Models default to the included coding model at standard speed. The ASD-STE100 terms-of-use check happens regardless, before anything from the spec or dictionary enters the repo or a linter.

## Answer (verbatim from the issue)

> ## Answers (Andrew, 2026-10-31)
>
> **Q4 card: scope and deciding metric**
> > Q: For the Simplified Technical English evaluation, what text is in scope and what metric decides?
> > A (verbatim): PLATE #1087: scope AGENTS.md, skills and MCP tool descriptions; decide on input tokens per task with success rate as a guardrail
>
> **Q5 card: test arms and adoption threshold**
> > Q: Which test arms, and what saving is enough to adopt?
> > A (verbatim): PLATE #1087: STE-lite only, adopt at 15%+ fewer input tokens with no drop in success rate
>
> **Mapped to the questions in this issue**
> 1. **Scope:** AGENTS.md, skills, and MCP tool descriptions. Out of scope for v1: CLI `--help`, issue/PR templates, wiki, agent output.
> 2. **Metrics:** input tokens per task decides; task success rate is a guardrail.
> 3. **Threshold:** adopt at 15% or more fewer input tokens per task with no drop in success rate.
> 4. **Models:** not asked on this card; default stays the included coding model at standard speed (per cost rules).
> 5. **Arms:** STE-lite only (the style prompt in #1086). No strict-STE arm.
> 6. **Licensing:** the ASD-STE100 terms-of-use check still happens regardless, before anything from the spec or dictionary goes into the repo or a linter.
>
> Recorded in the Epic body (#1086). `need:decision` removed. This Question still needs its `Closes #1087` research PR (`docs/research/`), which has not been opened.
>
> **Provenance / session notes**
> Andrew picked these on a multiple-choice card that the PM bot showed him in chat on 2026-10-31. The PM bot recorded them here.

## Answer signal


All six questions in the issue are answered (scope, metrics, threshold, models by existing default, strict vs STE-lite, licensing check). Answers are recorded in the Epic #1086 body, as the issue requires.

## Operating guidance

This answer does not change how agents work. `AGENTS.md` and `.agentic/skills.yml` are unchanged (`no-guidance-update`).
