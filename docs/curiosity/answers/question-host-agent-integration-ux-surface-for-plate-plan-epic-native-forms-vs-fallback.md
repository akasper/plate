# Answers for Question #275

**Title:** [Question]: Host-agent integration / UX surface for plate_plan_epic (native forms vs fallback)
**Issue:** #275

This file is generated from committed Answer Model data. GitHub comments remain the source of truth.

**Latest effective answer:** 2026-06-03T01:50:05.903506+00:00 by user

## Answer 1

- **Answer id:** 4608404419
- **Answered by:** user
- **Timestamp:** 2026-06-03T01:50:05.903506+00:00
- **Source:** cli-interactive
- **GitHub comment:** https://github.com/akasper/plate/issues/275#issuecomment-4608404419

```text
I don't have any specifics for the exact wire-up of #275. There may be per-CLI-tool capabilities, but I'm not yet sure how to implement those. I would also like to see a way to surface my own TUI widget as a fallback, but I'm not sure that that's possible either. One thing I notice is that both Grok Build and GitHub Copilot CLI have great TUI widgets they use for asking multiple choice questions, but it doesn't seem like there's any way for plugins to access or create those. In my ideal world, that's how it would work. (As a side note, if this ISN'T possible -- if I CAN'T trigger CLI-tool-native TUI forms -- then I may have to instead author my own PLATE TUI, because I consider this a key workflow for PLATE. This is where much of the value of the platform is added.) Do you have any suggestions?
```
