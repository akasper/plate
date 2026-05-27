# Copilot CLI Verification Harness Strategy

- **Issue:** #67
- **Researched by:** Copilot / plate_core automation
- **Date:** 2026-05-27
- **Status:** Completed

## Research Question

What is the most reliable way to verify the baseline agents and skills from CI, including discovery and simple delegation through Copilot CLI plugin surfaces?

## Sources

- `tests/test_cli.py`
- `tests/test_mcp.py`
- `tests/test_features.py`
- `src/plate_core/cli.py`
- `src/plate_core/mcp_server.py`
- `src/plate_core/features.py`
- `docs/research/custom-agent-packaging.md`
- `docs/research/stack-selection.md`
- `C:\\Users\\Andrew Kasper\\Documents\\Projects\\Personal\\plate_template\\docs\\playwright-e2e-guide.md`
- `C:\\Users\\Andrew Kasper\\Documents\\Projects\\Personal\\plate_template\\tests\\e2e\\README.md`

## Findings

### What is already reliable

The current plate_core tests already prove the stable parts of the runtime:

- CLI JSON output for health, epic status, feature detection, and bootstrap planning
- MCP tool call plumbing and error handling
- feature detection for installed plugin and runtime artifacts

That pattern is strong because it asserts the contract at the API boundary instead of depending on fragile transcript matching.

### What is risky

Directly automating an interactive Copilot CLI session is inherently more brittle than testing the runtime surfaces:

- session state can vary
- auth setup can change
- output formatting is easy to break
- interactive shells are slower and less deterministic than JSON-returning commands

### Recommended verification layers

| Layer | Purpose | Why it belongs |
|---|---|---|
| Unit tests | Validate catalog loading, CLI rendering, and MCP JSON payloads | Fast, deterministic, easy to keep green |
| Integration tests | Exercise repo-level feature discovery and plugin bundle wiring | Catches surface regressions |
| Interactive smoke tests | Optional sanity check for the Copilot CLI plugin persona and delegated tool access | Confirms the human-facing experience |
| Playwright-style artifact capture | Use only when the session is interactive and artifact-rich enough to justify it | Good for evidence, but not the primary correctness tool for a CLI session |

### Recommendation for the epic

1. Keep the authoritative tests in Python `unittest`/integration form for the runtime surfaces.
2. Add a small smoke harness for plugin install/discovery once the baseline catalog exists.
3. Capture transcripts/artifacts for the plugin experience, but do not make the entire feature depend on brittle transcript strings.
4. If Playwright is used, keep it at the orchestration layer and assert on structured outcomes, not loose human text.

## Recommendation

Use unit and integration tests as the primary verification path, then add a thin interactive smoke layer for the Copilot plugin experience. That balance gives the epic durable proof without overfitting the verification harness to transient CLI output.
