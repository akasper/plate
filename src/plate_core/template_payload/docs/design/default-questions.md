# Default PLATE Onboarding Questions

- **Issue:** #27
- **Designed by:** @copilot (agent session)
- **Date:** 2026-05-26
- **Status:** Draft

## Purpose

This file defines the minimum question set that every new PLATE project should answer during onboarding. These questions seed the repository's durable context, guide extension recommendations, and give agents enough structure to create the first Epic and first Feature issue without rediscovering the basics later.

## Default questions

| Order | Question | Why PLATE asks it | Primary destination |
|---|---|---|---|
| 1 | What is the project name and one-sentence purpose? | Anchors the repo's identity and prevents vague specs or issue titles. | `SPEC.md` vision / repository summary |
| 2 | Is this a new project or an existing codebase adopting PLATE? | Determines whether migration guidance and adoption tasks are needed. | Extension recommendations; bootstrap notes |
| 3 | Who are the primary users and what outcome matters most to them? | Keeps issue decomposition tied to user value. | `SPEC.md` personas and goals |
| 4 | How many contributors will actively work in this repository? | Influences review burden, wiki-sync value, and collaboration defaults. | Process defaults; extension recommendations |
| 5 | What tech stack do you prefer? (language, framework, package manager, data store) | Drives CI, test tooling, and agent working instructions. | `.github/copilot-instructions.md`; CI scaffolds |
| 6 | Where will the project be deployed first? | Helps choose infra and delivery extensions early. | `SPEC.md` constraints; follow-up infra issues |
| 7 | How should PLATE notify or escalate to humans? | Information goals only help if they reach the right people. | Process defaults; follow-up notification work |
| 8 | How budget-sensitive is this project? | Shapes automation, CI parallelism, and service recommendations. | `SPEC.md` constraints; cost-oriented Question issues |
| 9 | What testing posture should PLATE assume by default? | Lets the template suggest verification patterns immediately. | `tests/README.md`; `.github/copilot-instructions.md` |
| 10 | What first Epic and first Feature should PLATE help define next? | Converts onboarding into an actionable backlog instead of a static questionnaire. | Epic labels; starter issues |

## Default interpretation rules

- If the user does not specify an E2E framework, PLATE should assume **Playwright**.
- If the user does not know every answer yet, PLATE should capture the unresolved item as a `Question` issue instead of blocking the whole setup.
- Only stable defaults belong in machine-readable config; mutable planning state belongs in GitHub Projects fields.

## Expected outputs after the question set is answered

1. A short project summary
2. Extension recommendations
3. Initial Epic label suggestions
4. Stack-specific CI/test guidance
5. Follow-up `Question` issues for unanswered information goals

Closes #27
