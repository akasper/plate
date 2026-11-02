# Real World Tasks

Part of the PLATE agent operating rules (formerly in `AGENTS.md`). The always-loaded core is [AGENTS.md](../AGENTS.md).

## Real-world / external human Tasks (Epic planning requirement)

When planning or refining an Epic or Feature, the agent and human must explicitly identify any steps that require actions the AI development partner cannot safely or permissibly perform "in the real world" (external accounts, credential provisioning, manual deploys on third-party services, billing, legal, physical access, or any action requiring human identity/ownership on an external system such as PyPI trusted publisher setup, API key creation for CI, account creation, or initial manual publishes to unblock pins).

For each such step:
- Create a dedicated `Task` issue (labeled `Task`).
- Follow the standard human-only template in the body: "Human action required", "Why the agent cannot safely proceed", "Context and affected artifacts", "Best-effort instructions / next steps", and "Done signal" (the human leaves a short completion comment containing `<!-- PLATE-TASK-CLOSED -->`; the comment must not include secrets/credentials).
- Link the Task to the parent Epic (via sub-issue sidebar or milestone) and reference it from PR bodies, release checklists, Epic success criteria, and AGENTS.md notes.
- The Epic (and any dependent release) remains open until the human owner confirms completion of the real-world Task(s).

This makes the human dependencies first-class, visible, auditable, and part of the formal PLATE plan. The AI must not attempt to complete these Tasks. Examples from the PyPI deployment work: #625 (PyPI account + trusted publisher config for the publish workflow), #626 (initial back-publish of v0.7.2 via dispatch to unblock version-locked gh-plate installs), and the earlier #380 (marketplace package publish).

Planners must treat this as a required part of Epic scoping, not an afterthought in a PR description checklist. The guidance also applies to new-project templates (see template_payload/AGENTS.md) and the release ceremony packaging phase.

**gh-plate extension repo:** Do not force-push `akasper/gh-plate` `main`; if a history rewrite is unavoidable, announce it in release notes and document the reinstall command (`gh extension remove plate && gh extension install akasper/gh-plate`) for adopters (#1187).
