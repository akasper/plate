# Research closeout: Licensing text + CLA decision (#451)

**Parent Epic:** #390 (Add Licensing)  
**Related:** Feature implementation PR #455; Documentation #453 (Next Release targeting)

## Question
What exact LICENSE text, CONTRIBUTING language, metadata, and CLA posture should PLATE adopt for the source-available (MIT + Commons Clause) model?

## Decision (implemented)

| Item | Decision | Evidence |
|---|---|---|
| Filename | `LICENSE` (no extension) | GitHub license detection; landed at repo root |
| Copyright | `Copyright (c) 2026 Andrew Kasper` | `LICENSE` line 3 |
| Base | MIT License | Full MIT grant text in `LICENSE` |
| Restriction | Commons Clause License Condition v1.0 | Appended after MIT in `LICENSE` |
| README blurb | Free non-commercial/personal/internal; commercial/SaaS needs separate license | `README.md` licensing paragraph |
| CONTRIBUTING | Licensing / Copyright section points at `LICENSE` + Commons Clause summary | `CONTRIBUTING.md` |
| Metadata | Align package/plugin license fields with source-available posture | `pyproject.toml`, `plugin/plugin.json` (PR #455) |
| CLA | **Not now** | No multi-party contribution volume requiring CLA; Apache-style inbound=outbound via CONTRIBUTING is enough until commercial dual-license program needs a separate agreement |

## Acceptance criteria

- [x] Exact license text written and reviewed (issue body proposal + human-directed merge of #455)
- [x] Filename `LICENSE` justified and used
- [x] CONTRIBUTING licensing section landed
- [x] CLA decision recorded (**not now**; revisit if dual-license commercial program or external contributors demand it)
- [x] Metadata/classifier adjustments listed and applied in PR #455

## Verification (2026-07-27)

```text
LICENSE contains: MIT License, Copyright (c) 2026 Andrew Kasper, Commons Clause License Condition v1.0
README.md and CONTRIBUTING.md reference Commons Clause commercial restriction
Epic #390 target release hygiene: standing Next Release #612 (see #453)
```

## Follow-ups (out of scope for #451)

- Legal counsel re-read before any commercial dual-license offer (human / #451 residual judgment)
- Downstream template_payload license copy if not already aligned (Option C: core repo first)
- Human Tasks for marketplace publish remain separate (#380/#381/#626)

## Answer signal
Research complete: the authoritative text is the root `LICENSE` file as of release history including PR #455; this note is the durable decision record for CLA and contribution terms.
