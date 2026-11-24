# Point a repository at a custom PLATE process-docs endpoint

Use this guide when your team **forks or customizes** PLATE process documentation and
hosts it on your own Worker (or other static host) instead of the default
`https://plateprocess.dev` service.

Epic [#1508](https://github.com/akasper/plate/issues/1508); implementation [#1511](https://github.com/akasper/plate/issues/1511).

## Overview

| Piece | Default | Your fork |
|---|---|---|
| Website | `https://plateprocess.dev/` | `https://docs.example.com/` |
| MCP | `https://plateprocess.dev/mcp` | `https://docs.example.com/mcp` |
| Source | `akasper/plate` `docs/` at a release tag | Your fork's `docs/` at your tag |
| Repo pointer | `.plate` → `process_docs` | Same keys, your URLs |

Adopter repositories keep a **small pointer** in `.plate` and a **local fallback**
summary (`docs/plate/PROCESS_SUMMARY.md`). They do **not** need a full copy of PLATE
guides under `docs/`.

## 1. Fork or branch the docs source

1. Fork `akasper/plate` (or maintain a long-lived branch) with your process changes.
2. Keep doc edits in `docs/` and land them through normal reviewed PRs, same as upstream.
3. Tag releases when you want adopters to pin a doc version (for example `v0.12.1-acme`).

The reference Worker lives in `services/process-docs/` in the PLATE repository.

## 2. Build and deploy your endpoint

From a checkout on the **exact tag** you intend to serve:

```bash
git checkout vX.Y.Z-yourtag
cd services/process-docs
npm ci
npm run bundle:release
npx wrangler deploy
```

Configure your Worker custom domain (for example `docs.example.com`) in Cloudflare.
Do not commit API tokens; deploy stays operator-local unless your org adds its own CI.

The Worker serves:

- HTML for humans at `/` and `/<doc-path>`
- Read-only MCP at `/mcp` with `list_docs`, `get_doc`, `search_docs`

The MCP `version` argument is the **git tag** baked into `generated/bundle.json` at
build time, or `latest` for the deployment you just published.

See `services/process-docs/README.md` in the PLATE repo for bundle and test commands.

## 3. Point your adopter repo at the endpoint

Edit `.plate` (JSON):

```json
{
  "version": "1.4",
  "process_docs": {
    "base_url": "https://docs.example.com",
    "mcp_url": "https://docs.example.com/mcp",
    "version": "v0.12.1-acme"
  }
}
```

| Field | Meaning |
|---|---|
| `base_url` | Website origin (no trailing slash required) |
| `mcp_url` | MCP HTTP endpoint |
| `version` | Doc bundle tag adopters and agents should request |

After `gh plate import-payload --apply` or `gh plate config upgrade --apply`:

- **Default endpoint** (`https://plateprocess.dev`): `process_docs.version` is replaced
  by the **installed plate-core** release tag on each reconcile (import, upgrade, or
  repair). Re-run after you upgrade plate-core to pick up the matching docs tag.
- **Custom endpoint**: an explicit `version` pin is kept; only unset `version` gets
  the installed tag. Custom keys under `process_docs` (beyond `base_url`, `mcp_url`,
  `version`) are preserved across schema upgrade.

Re-run import or upgrade when you bump plate-core, then adjust overrides if you stay on
a custom host.

## 4. Versions and `latest`

- Each deploy bundles docs from the tag checked out at `npm run bundle:release`.
- Pin `process_docs.version` to that tag so agents call `get_doc(..., version="vX.Y.Z")`.
- On the default host, `latest` means “this deployment”. Custom hosts follow the same
  Worker semantics once you deploy a new bundle.

## 5. When the endpoint is unreachable

Each repo ships `docs/plate/PROCESS_SUMMARY.md` with a short offline summary and MCP
hints. It does not replace the full guide set.

If the service fails:

1. Use the fallback summary and repository `AGENTS.md`.
2. Fix networking or redeploy the Worker.
3. For air-gapped environments, temporarily keep a **local** doc tree (legacy copies)
   or vendor a static export—optional; upstream import no longer copies guides by default.

## 6. Linking from the default site

On `plateprocess.dev`, this page is available at
`migration/custom-process-docs-endpoint` after the Worker is deployed from a release
that includes this file.