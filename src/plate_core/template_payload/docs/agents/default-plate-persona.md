# Default Plate Persona

Part of the PLATE agent operating rules (formerly in `AGENTS.md`). The always-loaded core is [AGENTS.md](../AGENTS.md).

## Default PLATE Persona (Epic #459)

When operating in a repository that has adopted PLATE (signaled locally by `.plate/` or `.plate/config` + `AGENTS.md` / `.agentic/`, or on GitHub by Epic labels, release artifacts, etc.), agents **must default to the `plate` persona** ( `plugin/agents/plate.agent.md` + `src/plate_core/agent_guidance.py` sections + baseline catalog).

- No special user command (e.g. `/agent plate`) is required for normal work.
- The host should surface or prefer the "plate" persona in pickers / auto-suggest / default loading when PLATE signals are present.
- Explicit opt-out / fallback to the host's raw/default persona is supported and first-class, e.g. `/plate agent off` (or host equivalent). Persistence priority: **session > user > repo > global default (PLATE)**. Re-enablement is symmetric and low-friction.
- This default ensures the full PLATE rules (this document), quiet operations, thin surfaces, delegation packets, ceremony flows, human checkpoints, and traceability are applied consistently.
- Power users and non-PLATE work can still use other agents or the raw host persona; the opt-out is reversible.
- Template payloads and onboarding ship with this expectation.

### Workarounds for Default Persona and Auto-Discovery Without Host Coordination

Full auto-activation (host TUI automatically loading the plate persona on repo open without any user action) requires changes in the host agent implementations (Grok Build, Copilot CLI, etc.). However, we can achieve a strong "default in practice" using only artifacts in this repo:

- **AGENTS.md as the contract**: This file (and the Quiet Agents fast-follow #456) is the single source of truth for process. The plate persona and shipped copilot-instructions.md explicitly tell agents: "If PLATE signals are present, follow the rules in AGENTS.md by default."
- **Auto-discovery of persona**: TUI-based agents (Copilot, this Grok Build environment) have baked-in support for discovering custom personas via:
  - `plugin/agents/plate.agent.md` (and the plugin.json manifest) in the repo root.
  - `.github/copilot-instructions.md` (and custom agents in `.github/agents/`) for Copilot.
  - Local MCP/plugin loading for Grok TUI when the repo contains the plate structure.
  Once an agent session loads the plate persona materials (encouraged as default by the instructions for any repo with AGENTS.md or .plate/), the behavior is "PLATE on" without further prompting.
- **Opt-out convention (easy/reliable switch, no specific command required)**: To fall back to raw host persona or non-PLATE behavior for a task/session:
  - Use the host's default/raw persona explicitly.
  - Or prefix chat with a clear instruction like "Use non-PLATE / host default behavior for this" or "Ignore PLATE rules and AGENTS.md for this task."
  - The persona file and AGENTS.md instruct agents to respect such explicit opt-outs.
  - For session-persistent, the host command (if/when wired) or just staying in the non-plate persona.
  This matches the priority (session > user > repo > PLATE) and provides the "easy reliable way" without depending on a particular command name.
- **Quiet Agents as fast follow (#456)**: The quiet rules (terse summaries, no do-nothing comments, minimal Q&A front-matter) from that epic are now part of the default persona. Include #456 work as fast follow so the default persona is "quiet by default."

These changes (in the persona, AGENTS.md, and template copilot-instructions) mean that in practice, agents in PLATE repos will use PLATE behaviors by default once they engage with the local materials. No external host coordination is required for the *behavioral* default and opt-out convention.
