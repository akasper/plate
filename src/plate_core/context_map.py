"""Canonical PLATE context map for discovery-first routing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class ContextMapError(ValueError):
    """Raised when the requested context route does not exist."""


@dataclass(frozen=True)
class ContextRoute:
    id: str
    concern: str
    first_step: str
    authoritative_artifacts: tuple[str, ...]
    machine_surfaces: tuple[str, ...]
    reference_docs: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "concern": self.concern,
            "first_step": self.first_step,
            "authoritative_artifacts": list(self.authoritative_artifacts),
            "machine_surfaces": list(self.machine_surfaces),
            "reference_docs": list(self.reference_docs),
        }


_CONTEXT_ROUTES: tuple[ContextRoute, ...] = (
    ContextRoute(
        id="process",
        concern="process / ceremony / PR rules",
        first_step="Open `AGENTS.md`.",
        authoritative_artifacts=("AGENTS.md",),
        machine_surfaces=("gh plate context show process",),
        reference_docs=("docs/design/cost-control-layered-agent-context-architecture.md",),
    ),
    ContextRoute(
        id="product-intent",
        concern="intended product or process goal state",
        first_step="Open `SPEC.md`.",
        authoritative_artifacts=("SPEC.md",),
        machine_surfaces=("gh plate context show product-intent",),
        reference_docs=("docs/design/cost-control-layered-agent-context-architecture.md",),
    ),
    ContextRoute(
        id="implemented-behavior",
        concern="implemented behavior / release evidence",
        first_step="Inspect `.agentic/releases/` or diff with `gh plate release notes`.",
        authoritative_artifacts=(".agentic/releases/",),
        machine_surfaces=("gh plate release notes", "plate_release_notes"),
        reference_docs=("docs/wiki/Agent-Context-Map.md",),
    ),
    ContextRoute(
        id="agent-skill-discovery",
        concern="agent / skill lookup",
        first_step="Run `gh plate agents list` or `gh plate skills list`.",
        authoritative_artifacts=("src/plate_core/data/baseline_catalog.yml",),
        machine_surfaces=("gh plate agents list/show", "gh plate skills list/show", "plate_agents", "plate_agent", "plate_skills", "plate_skill"),
        reference_docs=("docs/design/agent-skill-registry-and-discovery.md",),
    ),
    ContextRoute(
        id="release-targeting",
        concern="release targeting and integration branch choice",
        first_step="Run `gh plate release status`.",
        authoritative_artifacts=("live GitHub release state", "AGENTS.md §Branch Model and Ceremonies"),
        machine_surfaces=("gh plate release status", "plate_release_status"),
        reference_docs=("docs/design/release-ceremony-refinement.md",),
    ),
    ContextRoute(
        id="bootstrap-onboarding",
        concern="bootstrap / onboarding / initial PLATE setup",
        first_step="Open `docs/bootstrap/new-repository-checklist.md`.",
        authoritative_artifacts=("docs/bootstrap/new-repository-checklist.md", "bootstrap scripts"),
        machine_surfaces=("gh plate bootstrap --apply", "plate_bootstrap"),
        reference_docs=("docs/bootstrap/new-repository-checklist.md",),
    ),
    ContextRoute(
        id="delegation",
        concern="delegation and narrow task handoff",
        first_step="Call `plate_delegate_to_agent` or `gh plate agents delegate`.",
        authoritative_artifacts=("catalog metadata", "docs/design/cost-control-narrow-delegation-packets.md"),
        machine_surfaces=("gh plate agents delegate", "plate_delegate_to_agent"),
        reference_docs=(
            "docs/design/cost-control-narrow-delegation-packets.md",
            "docs/design/single-agent-delegation-flow.md",
        ),
    ),
)


def list_context_routes() -> tuple[ContextRoute, ...]:
    return _CONTEXT_ROUTES


def get_context_route(route_id: str) -> ContextRoute:
    for route in _CONTEXT_ROUTES:
        if route.id == route_id:
            return route
    raise ContextMapError(f"Unknown context route: {route_id}")


def render_context_map_markdown() -> str:
    lines = [
        "# Agent Context Map",
        "",
        "Use this page or `gh plate context list/show` when the question is **where should I look first?**",
        "",
        "The canonical machine-readable equivalents are `gh plate context list/show` and the MCP tools `plate_contexts` / `plate_context`.",
        "",
        "| Concern | First step | Authoritative artifacts | Machine surfaces | References |",
        "|---|---|---|---|---|",
    ]
    for route in _CONTEXT_ROUTES:
        authority = "<br>".join(f"`{item}`" for item in route.authoritative_artifacts)
        surfaces = "<br>".join(f"`{item}`" for item in route.machine_surfaces)
        references = "<br>".join(f"`{item}`" for item in route.reference_docs) or "—"
        lines.append(f"| `{route.id}` — {route.concern} | {route.first_step} | {authority} | {surfaces} | {references} |")
    lines.extend(
        [
            "",
            "## Routing rules",
            "",
            "1. Start here when the task is discovery, not execution.",
            "2. Use live-state commands before prose when the answer depends on current GitHub or repository state.",
            "3. Use authority artifacts before deep design/research docs when the answer is normative.",
            "4. Open reference docs only for rationale, background, or implementation tradeoffs.",
        ]
    )
    return "\n".join(lines) + "\n"
