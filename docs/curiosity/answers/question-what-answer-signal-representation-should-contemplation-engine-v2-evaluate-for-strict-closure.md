# Answers for Question #326

**Title:** [Question]: What answer_signal representation should Contemplation Engine v2 evaluate for strict closure?
**Issue:** #326

This file is generated from committed Answer Model data. GitHub comments remain the source of truth.

**Latest effective answer:** 2026-06-05T12:14:44.942297+00:00 by copilot-agent

## Answer 1

- **Answer id:** 4631443674
- **Answered by:** copilot-agent
- **Timestamp:** 2026-06-05T12:14:44.942297+00:00
- **Source:** agent-contemplation
- **GitHub comment:** https://github.com/akasper/plate/issues/326#issuecomment-4631443674

```text
Provisional recommendation: treat `answer_signal` as an explicit structured section on the Question body, preserved in human-readable markdown but constrained to parseable line items. The engine should evaluate closure against those declared criteria plus cited evidence from the accumulated answer history; heuristic keywords like done/complete should never close a Question on their own. In practice, this means Contemplation Engine v2 should read the `Answer signal` section verbatim, normalize it into line-oriented criteria, and require each criterion to be satisfied or intentionally superseded before closing.
```
