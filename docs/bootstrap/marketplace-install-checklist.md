# Marketplace install + release checklist (#378 / #379)

Maintainer-facing verification for the **supported public** Copilot CLI and Grok Build marketplace install path. This is the durable closeout for packaging (#378) and docs/verification (#379).

**Not agent-completable:** real public package/marketplace publication remains human Tasks **#380**, **#381**, plus PyPI / trusted publisher Tasks **#625**, **#626** when pins require them.

## Surfaces (source of truth)

| Host | Marketplace manifest | Plugin payload |
|---|---|---|
| Copilot CLI | `.github/plugin/marketplace.json` | `plugin/` (`source: "plugin"`) |
| Grok Build | `.grok-plugin/marketplace.json` | local path `./.plugin` (generated mirror) |
| Runtime | `pip install -U 'plate-core==0.8.0'` → `plate-mcp` on `PATH` (pin matches public cut) | MCP via `plugin/.mcp.json` / `.plugin/.mcp.json` |

There is **no** separate GitHub-run “submit to marketplace” flow: this repository **is** the marketplace once manifests land on the default branch and consumers run `* plugin marketplace add akasper/plate`.

## User install (supported)

```sh
# Runtime prerequisite (required) — pin to the public cut, not an older lock
pip install -U 'plate-core==0.8.0'
python -c "import plate_core; print(plate_core.__version__)"  # expect 0.8.0

# Copilot CLI
copilot plugin marketplace add akasper/plate
copilot plugin install plate-core@plate-marketplace

# Grok Build
grok plugin marketplace add akasper/plate
grok plugin install plate-core@plate-marketplace --trust
# Then enable plugin, reload TUI, verify: grok inspect
```

Also keep **`gh extension install akasper/gh-plate`** (or `gh extension upgrade plate`) on **v0.8.0** so the thin shim `PLATE_CORE_VERSION` does not re-lock pip to 0.7.x mid-session.

Dev alternatives: local path install or `akasper/plate:plugin` — see root `README.md`.

## Maintainer verification (before release cut)

1. **Manifests**
   - Copilot: `.github/plugin/marketplace.json` → plugin `source` is `plugin`, version matches `plate_core.__version__`.
   - Grok: `.grok-plugin/marketplace.json` → `source.path` is `./.plugin`, version matches.
2. **Skills / index generators**
   ```sh
   python3 scripts/generate-plugin-skills.py --check
   python3 scripts/generate-grok-plugin-index.py --check
   ```
3. **Automated packaging gates**
   ```sh
   pytest tests/test_copilot_cli_marketplace_packaging.py -q
   ```
4. **Runtime prerequisite**
   - Documented as `pip install -U 'plate-core==0.8.0'` / `plate-mcp` on `PATH` in README.
   - Confirm `plate_core.__version__` and gh-plate pin both match the cut (see install parity research note).
5. **Smoke (when Copilot/Grok CLI available in environment)**
   ```sh
   copilot plugin marketplace add akasper/plate
   copilot plugin install plate-core@plate-marketplace
   ```
6. **Human publication Tasks (do not agent-complete)**
   - #380 — publish plate-core package for marketplace runtime
   - #381 — publish public Copilot CLI marketplace entry
   - #625 / #626 — PyPI trusted publisher + back-publish when gh-plate version pin requires it
7. **Release ceremony**
   - Fold marketplace work into active **Next Release** (#612) / versioned Release issue; never claim “1.0 marketplace done” without Task completion signals.

## Agent rules

- Prefer repo marketplace install commands in onboarding docs; do not invent a third marketplace host.
- Never auto-publish PyPI or marketplace listings; open/complete only Task templates with `<!-- PLATE-TASK-CLOSED -->` left for humans.
- Packaging build helpers (`plate_packaging_*`) produce review artifacts only — see #652 fragments.

## Related

- Features #378 (packaging surface), #379 (this verification/docs)
- Epic #377 (marketplace release track, if present)
- Human Tasks #380, #381, #625, #626
- Fragments: `652-marketplace-packaging-media-proof`, packaging budget gates under #634
