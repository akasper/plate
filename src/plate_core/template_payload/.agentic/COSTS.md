# PLATES Agentic Cost Log

Structured usage reports captured from closing comments on `Feature` and `Question` issues.

Agents should close those issues with a final comment that includes:

```text
=== USAGE REPORT ===
tokens: <integer>
cost: <$0.00>
duration: <hh:mm:ss>
=== END USAGE REPORT ===
```

`Task` issues are exempt from the usage-report block; they close with a completion comment containing `<!-- PLATE-TASK-CLOSED -->` instead.

When `.github/workflows/plates-on-issue-closed.yml` is enabled, closing comments on `Feature` and `Question` issues are harvested and appended as rows below. Do not edit rows manually unless correcting a bad harvest; prefer fixing the workflow or the closing comment format.

| Date (UTC) | Issue | Type | Tokens | Cost | Duration | Source |
|---|---|---|---|---|---|---|
