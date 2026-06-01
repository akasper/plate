# Goals

**This page is part of the PLATE convention for managing high-level project intent.**

Every PLATE project is encouraged to maintain a `Goals` page in its Wiki. This page serves as the canonical, agent-accessible source for the project's overall **mission** — why it exists and how it intends to succeed.

This is distinct from `SPEC.md`, which focuses on product implementation details, architecture decisions, and engineering outcomes.

## Purpose of This Page

The `Goals` page answers questions such as:
- Why is this project being built?
- Who is it for, and what outcomes matter most?
- What does "winning" look like at a strategic level (adoption, revenue, impact, etc.)?
- What are the key principles or constraints that should guide all major decisions?

Agents performing Information Audits (see Epic #218) are expected to read this page as one of their primary signals when identifying informational gaps.

## Mission

> **Example (for the PLATE project itself)**

PLATE exists to make reliable, high-velocity agentic software development the default way teams build on GitHub.

We are building the operating system for agent-driven development: a set of conventions, tools, and runtime surfaces that let AI agents own the majority of the software development lifecycle while preserving human judgment on risk, architecture, and direction.

---

**For your project**, replace the section above with your own mission statement. It should be broad and directional.

## Core Principles

**Example principles from the PLATE project** (adapt or replace for your own project):

- **GitHub is the Single Source of Truth**: All planning, execution, state, and knowledge should live in GitHub-native artifacts.
- **Agent Autonomy is the Default**: Agents should drive the majority of work, with humans focused on judgment and high-risk decisions.
- **Test-First is Non-Negotiable**: Verifiable progress through tests and evidence is a core value.
- **Lightweight and GitHub-Native**: The process should feel native and add minimal friction.
- **Evolvable and Extensible**: The system must scale from solo developers to large teams and support future surfaces.

## How We Intend to Succeed

**Broad strategic outcomes** (example for PLATE — replace with your project's equivalent):

- **Adoption**: Make it possible for any GitHub repository to adopt PLATE in under 15 minutes and immediately gain meaningful agentic leverage.
- **Agent Effectiveness**: Enable agents to reliably drive the majority of day-to-day development work.
- **Durability of Knowledge**: Create artifacts (especially answers to informational goals) that remain useful and discoverable over time.
- **Ecosystem Health**: Become a foundational layer that extensions, templates, and other tools build upon.

## Current State & Evidence

(Short, high-level snapshot — update periodically)

- PLATE core + template + MCP now support Curiosity/Q&A (Epic #139), baseline catalog, and the start of the Information Audit system (Epic #218).
- Research and design for Goals convention and audit contract complete; implementation in progress.

## Open Strategic Questions

Major unresolved informational goals related to the mission above should be tracked as `Question` issues. Agents performing Information Audits are expected to help discover and refine these.

**Examples of the kind of questions that belong here:**
- Strategic questions about customers, market, revenue model, positioning, etc.
- Fundamental "how will we succeed" questions that are not yet well understood.

---

**PLATE Convention Note**: This page is intended to be one of the primary inputs for the PLATE Information Audit system (see Epic #218). Projects adopting PLATE are encouraged to maintain a page like this in their Wiki so that agents working in the repository have clear access to the project's strategic intent.