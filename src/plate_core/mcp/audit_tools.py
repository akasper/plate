"""MCP tools for Information Audit (Epic #218, Feature #221).

Implements the core contract from Design #223 and modeling from #220:
- plate_perform_information_audit

The tool proposes Question issues (per the Goal / Informational Goal / Question
model) by scanning the project's Wiki Goals page + other surfaces. Supports
dry_run, scoping by agent_type, defaults inclusion, and provenance.

This is the "core engine" entrypoint. Generation uses simple heuristics + Goals
page signals for v1 (full LLM/open discovery + refinement in follow-ups).
Integrates with Curiosity/Q&A flows (proposed Questions feed list/prioritize).

Downstream PLATE adopters get this via the platform (template + MCP).
"""

from __future__ import annotations

import base64
import json
from typing import Any

from ..github_client import GhClient, GhApiError
from ..health import resolve_repo
from ..baseline_catalog import load_baseline_catalog


def _get_gh_client(client: GhClient | None = None) -> GhClient:
    return client or GhClient()


def _resolve_target_repo(repo: str | None) -> str:
    return resolve_repo(repo)


def _fetch_goals_content(gh: GhClient, target: str) -> str:
    """Best-effort fetch of docs/wiki/Goals.md (the convention home)."""
    try:
        resp = gh.api(f"repos/{target}/contents/docs/wiki/Goals.md")
        if isinstance(resp, dict) and resp.get("content"):
            return base64.b64decode(resp["content"]).decode("utf-8", errors="ignore")
    except (GhApiError, Exception):
        pass
    return ""


class PerformInformationAuditTool:
    """Core Information Audit engine.

    Per contract (#223) + model (#220):
    - Reads Goals page (primary strategic signal) + other surfaces (stubbed).
    - Proposes Questions with title, body (goal + samples + provenance + related),
      related_goals, provenance, priority_rationale, refinement_note.
    - Respects dry_run, max_questions, agent_type scoping, include_defaults.
    """

    @staticmethod
    def execute(
        repo: str | None = None,
        scope: str = "repo",
        agent_type: str = "general",
        max_questions: int = 5,
        dry_run: bool = False,
        include_defaults: bool = True,
        client: GhClient | None = None,
        **_kwargs: Any,
    ) -> dict[str, Any]:
        """
        Returns:
            {
                "repo": "...",
                "scope": "...",
                "agent_type": "...",
                "proposed_questions": [ {title, body, related_goals, provenance, ...}, ... ],
                "audit_log": "...",
                "dry_run": bool,
                "count": N
            }
        """
        gh = _get_gh_client(client)
        target = _resolve_target_repo(repo)

        goals = _fetch_goals_content(gh, target)

        proposed = []

        # Include platform + extension defaults from catalog (#222) when requested (#223 / audit contract)
        if include_defaults:
            try:
                catalog = load_baseline_catalog()
                for g in catalog.informational_goals:
                    proposed.append({
                        "title": g.title,
                        "body": g.body,
                        "related_goals": list(g.related_goals),
                        "provenance": g.provenance_hint or "Information Audit (catalog default)",
                        "priority_rationale": g.priority_rationale or "Default informational goal from platform catalog (#222).",
                        "refinement_note": g.refinement_note or "",
                    })
            except Exception:
                # Fallback (defensive; catalog should be present post #222)
                if not any("Mission" in p.get("title", "") for p in proposed):
                    proposed.append({
                        "title": "[Question]: Clarify project Mission and success criteria (Goals page)",
                        "body": "## Informational Goal\nWe need to know the project's explicit Mission...\n(Full details via catalog.)",
                        "related_goals": ["Mission"],
                        "provenance": "Information Audit (fallback)",
                        "priority_rationale": "Foundational.",
                        "refinement_note": "",
                    })

        # Goals-page driven proposal (per #220 model + #223 rules 1,2,9)
        if goals:
            has_mission = "Mission" in goals or "## Mission" in goals
            if not has_mission:
                proposed.append({
                    "title": "[Question]: Populate Mission section on the Goals wiki page",
                    "body": (
                        "## Informational Goal\n"
                        "We need to know the project's Mission (why we exist) so that Information Audits, "
                        "Question generation, and agent behavior can be grounded in explicit intent.\n\n"
                        "## Sample Questions\n"
                        "- What single sentence describes this project's purpose and target outcome?\n\n"
                        "## Provenance\n"
                        "Discovered via Information Audit (stub). Goals page exists but Mission section missing or weak.\n\n"
                        "## Related Goals\n"
                        "- Wiki Goals § Mission\n\n"
                        "## Refinement\n"
                        "After Mission, derive Core Principles and How We Intend to Succeed (see convention doc)."
                    ),
                    "related_goals": ["Mission"],
                    "provenance": "docs/wiki/Goals.md (present but Mission incomplete)",
                    "priority_rationale": "Blocks effective use of the Goals page by the audit engine and agents.",
                    "refinement_note": "",
                })
            else:
                # Example refinement
                proposed.append({
                    "title": "[Question]: Identify top 3 risks to the Mission (for Goals § Current State)",
                    "body": (
                        "## Informational Goal\n"
                        "We need to know the primary risks that could prevent achieving the Mission so the "
                        "Current State & Evidence section on Goals and risk-related Questions can be maintained.\n\n"
                        "## Sample Questions\n"
                        "- What are the top 3 risks to the Mission in the next 6-12 months?\n\n"
                        "## Provenance\n"
                        "Discovered via Information Audit (stub, agent_type=general). Goals page has Mission.\n\n"
                        "## Related Goals\n"
                        "- Wiki Goals § Mission\n- Wiki Goals § How We Intend to Succeed\n\n"
                        "## Refinement\n"
                        "This can be scoped to technical, market, or operational risks by agent_type."
                    ),
                    "related_goals": ["Mission", "How We Intend to Succeed"],
                    "provenance": "Information Audit stub on Goals page (Mission present)",
                    "priority_rationale": "Directly supports the 'Current State & Evidence' and 'Open Questions' sections of the convention.",
                    "refinement_note": "Can be refined by specialized agents (engineering vs marketing).",
                })

        # Cap and return (per contract #223 rules 3,4)
        proposed = proposed[:max_questions]
        return {
            "repo": target,
            "scope": scope,
            "agent_type": agent_type,
            "proposed_questions": proposed,
            "audit_log": (
                f"Stub audit run (dry_run={dry_run}). Scanned Goals page ({'present' if goals else 'missing'}). "
                f"Produced {len(proposed)} proposal(s) following #220 model + #223 contract (v1 heuristics; "
                "full open-ended + refinement + extensibility in subsequent commits for #221)."
            ),
            "dry_run": dry_run,
            "count": len(proposed),
        }


AUDIT_TOOLS = {
    "plate_perform_information_audit": PerformInformationAuditTool,
}
