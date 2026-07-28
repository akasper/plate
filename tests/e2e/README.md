# Plate Verification Harness

This is the end-to-end + structure verification harness for the plate-core plugin and CLI/MCP surfaces. It certifies **CLI-agnostic claims** (see Epic #205 / beta roadmap) so that plate works with Copilot, Grok Build, and future hosts without vendor lock-in in the manifests or guidance.

The harness exercises:
- Declarative plugin structure (`.plugin/`, `plugin.json`, agents, MCP wiring)
- Agent persona (baseline catalog references, required MCP tools like `plate_health`, `plate_what_next`, no vendor-specific language)
- CLI surfaces via `gh plate` (catalog discovery, health, etc.)
- Host-specific plugin install flows (example: Copilot)

## Prerequisites
- Node.js 18+ and npm
- For full host tests: the target CLI binary on PATH (e.g. `copilot`)
- Python 3 (for gh-plate driven catalog tests in some specs)

## Running the Harness
```bash
cd tests/e2e
npm install
npm test                 # runs all (host-specific tests auto-skip if binary absent)
npx playwright test plugin-structure.spec.ts   # structure/agnostic cert only
```

CI runs this as part of the full suite (see workflow for setup of copilot etc.).

## What "Passing" Means for Certification
- All structure tests pass (these are the core CLI-agnostic certification).
- Host install tests pass for the hosts under test (or are correctly skipped).
- Catalog and agent guidance surface the expected MCP tools and baseline entries.
- No regressions: future changes to manifests, agent.md, or core surfaces must keep the harness green.

## Running / Adapting for Your Own CLI Host
To certify a new host (or run against a custom build):

1. Ensure your CLI supports plugin installation from a local path, e.g.:
   `your-cli plugin install /path/to/plate-repo`
   (It should read `.plugin/plugin.json`, copy/symlink the agents/ and MCP config, and make `gh plate ...` (or equivalent) available.)

2. Copy/adapt `copilot-plugin.spec.ts` as a template:
   - Replace `copilot` / `runCopilot` with your binary and command wrapper.
   - Keep the install + uninstall + cleanup pattern.
   - Skip when your binary is not available.

3. Run the structure tests (they require no host binary) + your adapted host test.

4. Point the harness at a real or simulated plate install and confirm the agent can use plate MCP tools and guidance.

The `plugin-structure.spec.ts` + `catalog-discovery.spec.ts` provide a **host-independent simulation** of the contract. They can be run in any environment that has the plate source + node + python.

## Files
- `plugin-structure.spec.ts`: manifest + agent.md + MCP wiring + vendor-neutrality checks (the primary certification).
- `copilot-plugin.spec.ts`: real Copilot CLI install/uninstall flow (skippable).
- `catalog-discovery.spec.ts`: exercises `gh plate agents` / `skills` via the wrapper (baseline catalog).
- `compound-flows.spec.ts`: offline compound ceremony chains (babysit merge gates → release cut dry-run + finalize/sync plan → contemplate mutation PR draft) via `fixtures/compound_flow_driver.py` (#927 / #364 residual).
- `playwright.config.ts`, `tsconfig.json`: harness config.

## Updating the Harness
When adding MCP tools, agents, or surfaces:
- Update the expectations in `plugin-structure.spec.ts` (e.g. new `plate_*` tool mentions).
- Add or extend a catalog test.
- Update this README and the matching copy under `template_payload/tests/e2e/`.
- Author a fragment if the change affects the plugin surface story.

See also: `.plugin/`, `plugin/`, `src/plate_core/mcp_server.py`, baseline catalog, and docs on the CLI-agnostic / plugin model.
