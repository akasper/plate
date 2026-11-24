# Migrating from copied PLATE guides to plateprocess.dev

If your repository adopted PLATE **before** the process-docs service (#1508 / #1511),
`gh plate import-payload` likely copied PLATE guides under `docs/` or `docs/plate/`.

New imports **do not** copy those trees. They write:

- `.plate` → `process_docs` (endpoint + pinned PLATE version)
- `docs/plate/PROCESS_SUMMARY.md` (offline fallback)

## Existing adopters — nothing removed silently

Re-running import or upgrade:

- **Leaves** previously copied guide directories in place.
- **Updates** `process_docs.version` in `.plate` to match the installed plate-core release.
- **Refreshes** `docs/plate/PROCESS_SUMMARY.md` when content changes.
- Prints a note listing detected legacy guide paths when present.

You can continue to use local copies while transitioning agents to MCP and the website.

## Recommended transition

1. Run `gh plate import-payload --apply --strategy conservative` (or your usual upgrade path).
2. Confirm `.plate` contains `process_docs` (run `gh plate config upgrade --apply` if the schema was behind).
3. Point agents at `process_docs.mcp_url` for full guides (#1510).
4. When comfortable, delete legacy PLATE-only directories you no longer need, for example:
   - `docs/agents/`, `docs/bootstrap/`, `docs/design/`, … if they are unchanged template copies
   - Or the mirrored `docs/plate/...` tree from namespaced imports (#1015)

Keep **product** documentation and any customized wiki pages (for example `docs/wiki/Goals.md`).

## Resolves

- [#1503](https://github.com/akasper/plate/issues/1503) — imported guides conflicting with product `docs/` layout.
- Epic [#1508](https://github.com/akasper/plate/issues/1508) — hosted process docs + MCP.

Custom hosting: [custom-process-docs-endpoint.md](./custom-process-docs-endpoint.md).