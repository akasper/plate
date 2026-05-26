# Contributing to a PLATE Repository

This repository uses PLATE to keep human judgment, agent execution, and durable GitHub evidence aligned. Contributions should begin with a typed issue, proceed through testable implementation, and end with a pull request that links intent, evidence, documentation, and risk.

## Issue Rules

Every issue must carry exactly one issue type label: `Bug`, `Feature`, `Epic`, `Research`, `Design`, `Question`, `Audit`, or `Migration`. Feature and Epic issues must also carry exactly one `Epic: short-name` label. Question issues are information goals and are not tied to an Epic label. Mutable planning state such as status, priority, target date, owner, iteration, and release target belongs in GitHub Projects fields.

## Branch and Pull Request Rules

Use short descriptive branch names such as `feature/onboarding-copy`, `bug/login-regression`, or `docs/current-state-audit`. Every pull request must carry exactly one PR type label: `Bug`, `Feature`, or `Documentation`. Feature PRs must update `CURRENT.md`.

If a pull request is opened with GitHub CLI, include the type label in the create command itself, for example `gh pr create --label "Feature"`, instead of treating labeling as a separate best-effort follow-up step.

For batched Question triage through GitHub CLI, use `scripts/question_batch.sh` (or `scripts/QuestionBatch.ps1` on Windows) to list open Question issues quickly.

## Test-First Preference

Bug fixes should include regression coverage. Feature work should add or update tests before or alongside implementation. If a test cannot be automated yet, document the manual verification evidence and create follow-up work when automation is still required.

## Merge Authority

Agents and automation may prepare pull requests, but a human must approve merges, releases, permission changes, public claims, and any weakening of required gates.
