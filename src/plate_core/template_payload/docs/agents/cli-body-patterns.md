# Cli Body Patterns

Part of the PLATE agent operating rules (formerly in `AGENTS.md`). The always-loaded core is [AGENTS.md](../AGENTS.md).

## CLI Body Patterns (PowerShell safety)

When constructing `gh pr create` (or `gh issue create`) commands with multiline bodies, **never** embed literal `\n` sequences inside double-quoted strings from PowerShell. PowerShell does not interpret `\n` as a newline in this context; GitHub receives the literal backslash-n characters and the rendered description is broken (Bug #62).

**Recommended safe pattern (all environments):**

```bash
cat > /tmp/body.md << 'EOF'
## Summary
- First point
- Second point with details
EOF
gh pr create --base <base> --body-file /tmp/body.md --label Documentation ...
```

**PowerShell here-string (avoids all escaping pitfalls):**

```powershell
$body = @"
## Summary
- First point
- Second point
"@
Set-Content -Path $env:TEMP\body.md -Value $body -Encoding UTF8
gh pr create --base <base> --body-file $env:TEMP\body.md ...
```

Use `--body-file` (or the equivalent here-string + temp file) for every agent-authored multiline body. Update examples in this file and downstream docs when they are refreshed from upstream.
