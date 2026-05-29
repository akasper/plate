# Automatic Epic Creation

> **Status:** Superseded by milestone-based Epic planning.  
> **Issue:** #28  
> **Superseded by:** [`docs/design/native-github-pr-integration.md`](../design/native-github-pr-integration.md)  
> **Historical analysis:** [`docs/research/automatic-epic-creation.md`](../research/automatic-epic-creation.md)

## Summary

This page documents a now-superseded idea: automatically creating `Epic: short-name` labels and stub Epic issues. PLATE now treats GitHub Milestones as the canonical Epic container, so the preferred path is to create the milestone directly and assign the related issues and pull requests to it.

## Recommended Approach

**Superseded recommendation:** do not build label auto-creation.

A GitHub milestone should be created directly when a new Epic is opened. Optional Epic issues may still exist for narrative/design artifacts, but they no longer own a dedicated `Epic:` label.

## Options Considered

| Option | Description | Verdict |
|---|---|---|
| A — Milestones as Epics | Use GitHub milestones directly for Epic identity and grouping | **Adopted** |
| B — Auto-create `Epic:` labels | Free-form input + workflow that creates label/Epic on demand | Rejected: duplicates milestone behavior |
| C — Status quo | Continue manual label and Epic issue management | Rejected: keeps unnecessary custom metadata alive |

## Current Design Decisions

1. Milestones, not `Epic:` labels, are the source of truth for new Epic planning.
2. Feature and optional Epic issues should be milestoned directly.
3. Issue-driven PRs may satisfy traceability with closing keywords or Development sidebar links.
4. Delete branch on merge remains configurable but should default to on for PLATE repositories.

## Implementation Artifact

The historical workflow sketch remains in the research document for reference only. New implementation work should follow the milestone-based design in `docs/design/native-github-pr-integration.md`.
