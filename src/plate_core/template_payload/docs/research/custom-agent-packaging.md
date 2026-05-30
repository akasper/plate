# Custom Agent Packaging for PLATE Repositories

- **Issue:** #23
- **Researched by:** @copilot (agent session)
- **Date:** 2026-05-25
- **Status:** Completed

## Research Question

What is the best way to package custom agents (e.g., a marketing or research agent) for Copilot CLI directly via the `plate_template` template repository? Can agents be packaged according to the PLATE `extension` methodology?

## Sources

- [Custom agents configuration — GitHub Docs](https://docs.github.com/en/copilot/reference/custom-agents-configuration)
- [Creating custom agents for Copilot — GitHub Docs](https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/customize-cloud-agent/create-custom-agents)
- [About custom agents — GitHub Docs](https://docs.github.com/en/copilot/concepts/agents/copilot-cli/about-custom-agents)
- Existing PLATE extension registry (`.agentic/extensions.yml`)
- Existing PLATE skills registry (`.agentic/skills.yml`)

## Findings

### Mechanism: `.github/agents/` Directory

GitHub Copilot supports **custom agents** defined as Markdown files with YAML frontmatter, stored in:

| Scope | Location | Visibility |
|---|---|---|
| Repository (team) | `.github/agents/<name>.agent.md` | All repo collaborators |
| Organization | `<org>/.github/agents/<name>.agent.md` | All org members |
| Personal | `~/.copilot/agents/<name>.agent.md` | Single user only |

Each `.agent.md` file is self-contained and defines:

```yaml
---
name: <display-name>
description: <required — agent purpose>
tools:
  - <tool1>
  - <tool2>
model: <optional model override>
user-invocable: true
---

<Instructions body — up to 30,000 characters>
```

### Comparison: Prompt Files vs. Custom Agents

| Aspect | `.github/prompts/*.prompt.md` | `.github/agents/*.agent.md` |
|---|---|---|
| Purpose | Reusable one-shot prompt templates | Persistent agent personas with sustained context |
| Complexity | Single instruction block | Multi-tool, multi-step workflows |
| Session state | Stateless (one response) | Stateful (agent retains context across turns) |
| Tool access | Inherits caller's tools | Declares its own tool set |
| Invocation | Referenced as prompt shortcut | Selected from agent picker or `@agent-name` |

### Options Evaluated

| Option | Approach | Pros | Cons |
|---|---|---|---|
| A | Ship `.agent.md` files directly in `.github/agents/` | Native GitHub support, zero maintenance, instant availability to all collaborators | Agents directory not customizable beyond frontmatter |
| B | Ship prompt files in `.github/prompts/` | Simpler, reusable building blocks | No persistent persona, limited to one-shot | 
| C | External MCP server hosting agent logic | Maximum flexibility, external tool integration | Heavy maintenance, requires hosting, overkill for template |
| D | `copilot-instructions.md` inline personas | No extra files | Pollutes global instructions, hard to select one persona |

### Decision Criteria Assessment

| Criterion | Winner |
|---|---|
| Least maintenance | **Option A** — files are static Markdown, no infrastructure |
| Easiest to understand | **Option A** — single self-contained file per agent |
| PLATE extension compatibility | **Option A** — artifacts list naturally fits `.agentic/extensions.yml` |
| Template distribution | **Option A** — files copy with `git clone` / GitHub template instantiation |
| Copilot CLI + IDE + github.com support | **Option A** — all three platforms read `.github/agents/` |

### PLATE Extension Integration

Custom agents fit the PLATE extension model perfectly:

1. **Extension entry** in `.agentic/extensions.yml` declares the agent files as artifacts.
2. **Skill entry** in `.agentic/skills.yml` constrains what the agent may modify.
3. **Agent file** in `.github/agents/` provides the Copilot-native definition.
4. **Documentation** in `docs/` explains purpose and usage.

This three-layer approach (extension registry → skill constraint → native agent file) preserves PLATE's evidence-based governance while leveraging GitHub's native agent infrastructure.

### Reference Implementation: PLATE Configurator Agent

The recommended first agent is a **PLATE Configurator** that:
- Guides users through initial repository setup
- Asks questions about project type, team size, and workflow preferences
- Recommends which PLATE extensions to enable
- Generates appropriate label taxonomy and project fields

This agent demonstrates the packaging pattern and provides immediate value to template adopters.

## Recommendation

1. **Adopt Option A** — ship custom agents as `.agent.md` files in `.github/agents/`.
2. **Register each agent** as an extension in `.agentic/extensions.yml` with `default_enabled: true`.
3. **Constrain each agent** with a corresponding skill in `.agentic/skills.yml`.
4. **Include a reference implementation** (`plate-configurator.agent.md`) in the template.
5. **Document the pattern** so downstream teams can add their own domain-specific agents (marketing, research, QA, etc.) following the same structure.

### Follow-up Actions

- New issue: Create additional domain-specific agent examples (marketing agent, research agent)
- Update internal documentation with agent authoring guidance
- Add agent linting to CI (validate frontmatter schema)
