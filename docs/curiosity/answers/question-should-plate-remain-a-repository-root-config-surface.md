# Answers for Question #327

**Title:** [Question]: Should .plate remain a repository-root config surface?
**Issue:** #327

This file is generated from committed Answer Model data. GitHub comments remain the source of truth.

**Latest effective answer:** 2026-06-05T12:14:46.055634+00:00 by copilot-agent

## Answer 1

- **Answer id:** 4631443806
- **Answered by:** copilot-agent
- **Timestamp:** 2026-06-05T12:14:46.055634+00:00
- **Source:** agent-contemplation
- **GitHub comment:** https://github.com/akasper/plate/issues/327#issuecomment-4631443806

```text
Provisional recommendation: keep `.plate` at the repository root. The existing epic, design, and implementation language all define it as repo-owned root configuration, which makes it visible to both humans and tooling without coupling it to GitHub-only metadata under `.github/`. Future CLI, MCP, bootstrap, and extension flows should therefore continue treating root placement as the canonical location, with `.github/` reserved for GitHub-native automation artifacts rather than core project configuration.
```
