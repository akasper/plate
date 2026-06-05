# Answers for Question #319

**Title:** [Question]: How should a new PLATE repository create and repair standing release-track issues and branches?
**Issue:** #319

This file is generated from committed Answer Model data. GitHub comments remain the source of truth.

**Latest effective answer:** 2026-06-04T00:48:25Z by akasper

## Answer 1

- **Answer id:** 4617960226
- **Answered by:** akasper
- **Timestamp:** 2026-06-04T00:48:25Z
- **Source:** summary-backfill
- **GitHub comment:** https://github.com/akasper/plate/issues/319#issuecomment-4617960226

```text
Research summary:

- Canonical standing target: one open `Release` issue titled `Next Release`, not separate Major/Minor/Patch release issues.
- Initial standing branch creation belongs to `gh plate bootstrap --apply`; packaging rollover belongs to `gh plate release finalize`; repair should be a dedicated idempotent init/repair command.
- Healthy vs never-initialized vs drifted state is now documented in `docs/research/release-track-bootstrap-and-repair.md`.
- Follow-up implementation gap is tracked in #320.

Documentation PR: #321
```
