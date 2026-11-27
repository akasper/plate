# PLATES Agentic Cost Log

Structured usage reports captured from closing comments on `Feature` and `Question` issues. Rows are appended by `.github/workflows/plates-on-issue-closed.yml` when those issues close with a valid `=== USAGE REPORT ===` block (see AGENTS.md §Issue Artifact Rules). An empty table is normal until the first qualifying close.

| Date (UTC) | Issue | Type | Tokens | Cost | Duration | Source |
|---|---|---|---|---|---|---|
