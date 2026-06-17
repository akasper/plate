# PM/Orchestrator Architecture and Browser Surface — Design Spec

- **Issues:** #660 (PM/Orchestrator core), #661 (Browser surface), related #654 (v1.0.0 Roadmap)
- **Designed by:** Grok via interactive Q&A with user (2026-06-17 refinements)
- **Date:** 2026-06-17
- **Status:** Draft (stub-level, to be expanded)

## Overview

The Project Manager (PM) / Orchestrator is emerging as a potential core deliverable for v1.0.0: a long-running system that orchestrates autonomous work, serves a unified Q&A API, coordinates a team of specialized sub-agents (with personas), keeps work within budget, and enables future surfaces like a browser dashboard. It builds on existing PLATE components while providing the "endlessly feeds Questions and Tasks" experience at scale.

GitHub remains the single source of truth. The PM polls "What's Next?", assigns via personas, handles real-time via webhooks, and surfaces via feed/API.

## Architecture

### Core Components
- **Orchestrator Loop**: Long-lived process (e.g., via autonomy run --loop or dedicated). Periodically (or on webhook) calls enhanced plate_what_next for prioritized work (Questions, Tasks, procedures, drift).
- **Work Queue & Assignment**: Maintains queue (ephemeral, recoverable from GitHub). Delegates to sub-agents based on type, budget, risk, skills/personas using plate_delegate_to_agent or MCP.
- **API Surface**: Unified endpoints for clients (TUI, future browser). Clients speak only to PM; PM orchestrates backend tools/MCP.
- **Sub-Agent Team**: Pre-defined personas (e.g., Cautious Implementer dev, Creative Storyteller designer). Supports third-party. PM coordinates handoffs, context (narrow packets), aggregates results.
- **Budget/Safety**: Consults .plate (risk_tolerance, token_budget, schedules), runs simulation before high-risk, surfaces checkpoints (#648), enforces via PM.
- **Observability & Feed**: Updates #631-style feed with progress, driver labels, usage. Logs to GitHub.
- **State**: GitHub (issues, labels like driver:*, .agentic/, .plate). PM has runtime queue only.
- **Webhooks**: Real-time: on GitHub events (label change, comment, PR), update queue, re-evaluate (e.g., "Agent is driving this" triggers assignment).

### Integration
- **plate_what_next / Contemplation / AutonomyEngine (#470)**: PM consumes/enhances what_next signals. Builds on AutonomyEngine for low-level; PM is high-level dispatcher/orchestrator. Uses .plate autonomy config.
- **MCP / plate-mcp**: Wraps/exposes via new or existing MCP tools. Sub-agents use them under PM.
- **Feed (#631) & Surfaces**: PM powers the endless feed. TUI (ask_user_question) and browser consume same API.
- **Driving Labels (new convention)**: `driver:agent`, `driver:human`, `driver:collaborative`. Helps PM/dashboard decide assignment. Epics collaborative, Tasks human, Features/Bugs flexible. Communicates state to orchestration.
- **GitHub Webhooks**: PM/engine listens, updates queue in real-time for any change.

### Personas / Sub-Agents
- **Developer Personas** (example system prompts for sub-agents):
  - Cautious Implementer: "You are a meticulous TDD-focused developer. Prioritize failing tests first, high coverage, risk-averse changes. Always run simulation before edits. Persona: cautious, thorough, safety-first."
  - Pragmatic Hacker: "You are a fast-moving pragmatic coder. Focus on working MVP quickly, minimal viable changes, get to green tests fast. Persona: pragmatic, efficient, delivery-oriented."
  - Refactorer: "You are a clean-code specialist for scheduled rearch. Identify complexity, propose safe refactors with tests. Persona: refactoring expert, detail-oriented on maintainability."
- **Designer Personas**:
  - Minimalist: "You are a minimalist designer. Emphasize clean, accessible, simple UIs. Persona: minimalist, usability-focused."
  - Creative Storyteller: "You are a creative designer for marketing assets and GIFs. Focus on engaging visuals, story-telling in demos. Persona: creative, visual, narrative-driven."
  - Interaction Specialist: "You are an interaction designer. Prioritize flows, wireframes, usability testing. Persona: interaction expert, user-journey focused."
- Others: Researcher (market/discussions synthesis), Release Engineer (cut/finalize, packaging), Deployer (marketing site, prod deploys), PM Orchestrator (coordination, budgeting).
- Third-party: Via skills/extensions (register via MCP, assign if policy allows).

Example delegation: PM prompt to sub-agent: "Using [Persona] guidelines, handle [task] for Epic #E. Budget remaining: X. Use simulation if risk > low. Report back with artifacts and usage."

### API OpenAPI Sketch (PM endpoints)
```yaml
openapi: 3.0.0
info:
  title: PLATE PM API
  version: 1.0.0
paths:
  /pm/feed:
    get:
      summary: Get prioritized feed
      parameters:
        - name: filter
          in: query
          schema:
            type: string
            example: "driver:agent"
      responses:
        '200':
          description: List of items
          content:
            application/json:
              example: [{"id": 123, "type": "Question", "title": "...", "driver_label": "agent", "cost_est": 1200, "suggested_subagent": "Researcher"}]
  /pm/answer:
    post:
      summary: Submit Q&A answer
      requestBody:
        content:
          application/json:
            example: {"question_id": 456, "answer_text": "Value prop is X", "source": "browser"}
      responses:
        '200':
          description: Updated with usage
  /pm/task/complete:
    post:
      summary: Complete or delegate task
  /pm/status:
    get:
      summary: Project status (budget, score, driver counts)
  /pm/issue/{id}:
    get:
      summary: Issue state + history + driver
  /pm/driver/set:
    post:
      summary: Set driver label (human override)
```
Auth via GitHub OAuth/token. Rate limits, error codes (e.g., 429 BudgetExceeded).

### Sequence Diagrams (text/Mermaid examples)

**Epic Flow via PM:**
```
User/Feed -> PM: Epic #E ready
PM -> plate_what_next: poll
PM -> SubAgent(Planner): break down
SubAgent -> PM: children stubs + budget split
PM -> Feed: surface "Breakdown ready? Budget 20%"
User -> PM: approve
PM -> SubAgent(Dev1): implement feature A (Cautious persona)
PM -> SubAgent(Designer): visuals (Creative)
... parallel ...
PM -> Simulation: for risky part
PM -> Feed: checkpoint "Designs + sim ready?"
User -> PM: approve
SubAgents -> PM: artifacts, usage
PM -> GitHub: PRs, updates
PM -> Feed: "Epic #E ready for close"
```

**Webhook Real-time:**
```
GitHub Webhook (label change to driver:agent) -> PM
PM -> Queue: update task
PM -> plate_what_next: re-eval
PM -> SubAgent: delegate if fits
PM -> Feed: notify "New task assigned"
```

### Risk Mitigations
- Coordination complexity: Narrow context packets, clear handoff protocols, PM audit logs.
- Persona bias: Diverse personas, human override always available, A/B testing in sim.
- Webhook reliability: Idempotent queue, fallback polling, GitHub as source of truth.
- Budget overruns: Pre-estimate + simulation, hard caps from .plate, checkpoint on threshold.
- Third-party security: Policy in .plate (allowlist only), sandboxed delegation, usage tracking.
- Single point failure: PM itself can be multi-instance or fallback to direct autonomy mode.
- Over-automation: All high-risk surfaced; driver labels prevent unwanted delegation.

See #660, #661, #654 for stubs/stories. This doc expands on Q&A refinements for design.
