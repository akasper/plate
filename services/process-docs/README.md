# plateprocess.dev (`services/process-docs`)

Cloudflare Worker **`plate-docs`** serves PLATE process documentation from the repo `docs/` tree that was present at **build time** for a **git release tag**:

- **Website:** `https://plateprocess.dev/` (index) and `https://plateprocess.dev/<doc-path>` (Markdown → HTML)
- **MCP:** `https://plateprocess.dev/mcp` — read-only `list_docs`, `get_doc`, `search_docs`
- **Health:** `GET /health` → `ok`

Epic [#1508](https://github.com/akasper/plate/issues/1508).

## Versioning (git tags, not Worker URL paths)

There are **no** `/latest/` or `/v0.12.0/` URL prefixes. The served version is whatever **release tag** you had checked out when you ran `npm run bundle` before deploy. MCP `version` must be that tag or `latest` (meaning “this deployment”).

To publish docs for a new PLATE release, check out that tag, bundle, and deploy manually.

## Build bundle

```bash
git checkout vX.Y.Z    # exact release tag
cd services/process-docs
npm ci
npm run bundle:release # requires exact release tag; writes generated/bundle.json
npm test
```

## Manual deploy

From the same tagged checkout (after `npm run bundle:release`):

```bash
cd services/process-docs
npm run bundle:release
npx wrangler deploy
```

No GitHub Actions deploy workflow and no Cloudflare secrets in this repository—operators run Wrangler locally with their own Cloudflare credentials.

`wrangler.toml` sets `workers_dev = false` and `preview_urls = false`. The Worker has no write bindings (read-only, Free-plan friendly).

## Local development

```bash
cd services/process-docs
npm ci
npm run bundle
npm run dev
```

Unit tests use `DOC_SOURCE=fixture` (no bundle required for `npm test` beyond the stub `generated/bundle.json`).

```bash
curl -sS http://127.0.0.1:8787/health
curl -sS "http://127.0.0.1:8787/wiki/Home" | head
curl -sS http://127.0.0.1:8787/mcp \
  -H 'Content-Type: application/json' -H 'Accept: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

## CI

Root `CI` runs `npm test` and `npm run check:links` under this directory.