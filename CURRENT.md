---
status: "deprecated"
replacement: ".agentic/releases/"
deprecated_at: "2026-05-30"
---

# Deprecated

`CURRENT.md` is deprecated in this repository.

Use versioned per-feature change files under `.agentic/releases/` as the durable source of implemented-state and migration evidence.

For agent-friendly migration steps, render release guidance with:

```bash
python scripts/render_release_migrations.py .agentic/releases/
```

This stub remains only for backward compatibility with older automation and documentation links.
