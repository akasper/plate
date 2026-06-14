# Contributing to a PLATE Repository

This repository uses PLATE to keep human judgment, agent execution, and durable GitHub evidence aligned. Contributions should begin with a typed issue, proceed through testable implementation, and end with a pull request that links intent, evidence, documentation, and risk.

## Licensing and Contributions

This repository is licensed under the terms described in the [LICENSE](LICENSE) file at the root (a permissive base license subject to the Commons Clause License Condition v1.0, which restricts commercial use, resale, or SaaS offerings without a separate license from the copyright holder).

**Summary for users:** Free for non-commercial, personal, or internal use and modification. Commercial use, resale, or SaaS offerings require a separate license.

By submitting a contribution (for example, a pull request or patch), you agree that the contribution is provided under the same license terms as the project.

See the full text in the LICENSE file, including the Commons Clause.

(If a formal CLA or additional contribution agreement is adopted in the future, it will be referenced here.)

## Issue Rules

Every issue must carry exactly one issue type label: `Bug`, `Feature`, `Epic`, `Release`, `Research`, `Design`, `Question`, `Task`, `Audit`, or `Migration`. Feature issues, and optional Epic issues when used, must also be assigned to the GitHub milestone that represents the Epic. Question issues are information goals and are not tied to an Epic milestone by default. Task issues may be standalone or inherit an Epic milestone when clearly Epic-related, but they do not require an `Epic:` label and close with a completion comment containing `<!-- PLATE-TASK-CLOSED -->`. Mutable planning state such as status, priority, target date, owner, iteration, and release target belongs in GitHub Projects fields.

## Branch and Pull Request Rules

PLATE uses a three-tier branch model: `epic/<short-name>` branches for feature work within an Epic, a persistent `release` branch for Epic integration, and `main` for stable tagged releases. Feature and Bug PRs should target the epic branch for their Epic. When all child issues in an Epic are resolved, open a PR from `epic/<name>` → `release` (Epic-close ceremony). When a release is ready, open a PR from `release` → `main`, apply a semver tag, and hard-reset `release` to the tag (Release ceremony). See `AGENTS.md §Branch Model and Ceremonies` for the full step-by-step guide.

Use short descriptive branch names such as `feature/onboarding-copy`, `bug/login-regression`, or `docs/current-state-audit`. PR titles must be clean and written for human readers — do not use any bracketed prefixes (e.g. `[Feature]`, `[Bug]`, `[Documentation]`, `[WIP]`, `WIP:`, `[DRAFT]`, `DRAFT:`, or similar) and do not put issue references such as `(Closes #N)` in the title. All metadata lives in GitHub's native fields (labels, Development sidebar or body closing keywords, draft status, milestones). See AGENTS.md for details. Every pull request must carry exactly one PR type label: `Bug`, `Feature`, or `Documentation`. Feature PRs that change PLATE process, templates, or agent surfaces must author a fragment under `.agentic/releases/unreleased/<slug>.json`.

Use clean, descriptive PR titles that summarize the change without legacy status prefixes. Do not use `[WIP]`, `WIP:`, `[DRAFT]`, `DRAFT:`, or similar prefixes in titles. Use GitHub's native Draft PR status instead (`gh pr create --draft` or the "Create draft pull request" option in the UI) to signal work-in-progress. Draft status is reversible and keeps titles readable in PR lists, search results, notifications, and commit history.

If a pull request is opened with GitHub CLI, include the type label in the create command itself, for example `gh pr create --label "Feature"`, instead of treating labeling as a separate best-effort follow-up step.

When a pull request belongs to an Epic, set its milestone to match the Epic milestone. `Feature`, `Bug`, and issue-driven `Documentation` PRs must also link at least one tracked issue using either a closing keyword in the PR body or the Development sidebar. Use `no-issue` only for true chores or maintenance PRs that intentionally do not resolve tracked work.

For batched Question triage through GitHub CLI, use `scripts/question_batch.sh` (or `scripts/QuestionBatch.ps1` on Windows) to list open Question issues quickly.

## Test-First Preference

Bug fixes should include regression coverage. Feature work should add or update tests before or alongside implementation. If a test cannot be automated yet, document the manual verification evidence and create follow-up work when automation is still required.

## Merge Authority

Agents and automation may prepare pull requests, but a human must approve merges, releases, permission changes, public claims, and any weakening of required gates.
