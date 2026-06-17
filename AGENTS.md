# PLATE Agent Operating Rules

This repository follows the **Process Lifecycle Agentic Task Engine (PLATE)** methodology. The local operating doctrine is simple: **humans keep judgment, agents do the toil, and GitHub preserves truth**.

Agents working here should treat repository artifacts as durable project memory, not as optional narrative. Issues, labels, tests, pull requests, per-feature change files in `.agentic/releases/`, wiki pages, release notes, audit outputs, and traceability records are the inspectable record of the project.

## Authority Model

The PLATE book explains doctrine and the reasons behind the method. This repository is the source of truth for the **plate_core runtime implementation** — the shared library, `gh plate` extension, and `plate-mcp` MCP server that implement PLATE platform tooling. When a repository artifact and book prose disagree, do not preserve both versions indefinitely. Open a corrective issue or pull request that reconciles the doctrine, the implementation artifact, and any migration note required for downstream users.

| Area | Agent May Do | Human Must Decide |
|---|---|---|
| Product intent | Draft proposals, clarify ambiguities, identify conflicts, and map work to issues. | Final scope, priority, product tradeoffs, public commitments, and roadmap direction. |
| Implementation | Modify code, tests, docs, and configuration inside an approved task. | Acceptance of risk, merge approval, release approval, and irreversible operational changes. |
| Process | Follow PLATE rules, detect drift, and suggest process improvements. | Changing required gates, weakening checks, changing merge policy, or adopting new required automation. |
| Documentation | Update per-feature change files under `.agentic/releases/`, wiki source pages, release notes, audit notes, and traceability records. | Approving claims that affect customers, pricing, legal posture, security posture, or roadmap promises. |
| Stack selection | Prototype and benchmark candidate stacks per the Research issue. | Final language/runtime choice and distribution format. |

## Real-world / external human Tasks (Epic planning requirement)

When planning or refining an Epic or Feature, the agent and human must explicitly identify any steps that require actions the AI development partner cannot safely or permissibly perform "in the real world" (external accounts, credential provisioning, manual deploys on third-party services, billing, legal, physical access, or any action requiring human identity/ownership on an external system such as PyPI trusted publisher setup, API key creation for CI, account creation, or initial manual publishes to unblock pins).

For each such step:
- Create a dedicated `Task` issue (labeled `Task`).
- Follow the standard human-only template in the body: "Human action required", "Why the agent cannot safely proceed", "Context and affected artifacts", "Best-effort instructions / next steps", and "Done signal" (the human leaves a short completion comment containing `<!-- PLATE-TASK-CLOSED -->`; the comment must not include secrets/credentials).
- Link the Task to the parent Epic (via sub-issue sidebar or milestone) and reference it from PR bodies, release checklists, Epic success criteria, and AGENTS.md notes.
- The Epic (and any dependent release) remains open until the human owner confirms completion of the real-world Task(s).

This makes the human dependencies first-class, visible, auditable, and part of the formal PLATE plan. The AI must not attempt to complete these Tasks. Examples from the PyPI deployment work: #625 (PyPI account + trusted publisher config for the publish workflow), #626 (initial back-publish of v0.7.2 via dispatch to unblock version-locked gh-plate installs), and the earlier #380 (marketplace package publish).

Planners must treat this as a required part of Epic scoping, not an afterthought in a PR description checklist. The guidance also applies to new-project templates (see template_payload/AGENTS.md) and the release ceremony packaging phase.

## Default PLATE Persona (Epic #459)

... (rest of file continues unchanged from the current version; the above is inserted as a new top-level section after the Authority Model table and before the Default PLATE Persona section for visibility during Epic planning)