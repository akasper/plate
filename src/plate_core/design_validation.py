"""First-class design validation + visual/interaction contracts (#646).

Every Feature can carry an enforceable design contract:
- Visual specs / wireframe refs
- Interaction acceptance criteria
- Automated validation hooks (Playwright, visual regression, axe)
- User approval of the contract during planning/refinement

Durable under .agentic/design_contracts/. Complements feature_loop (#639) and
design_research_approval (#632) — contracts are the testable spec, not demos.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CONTRACTS_DIR = Path(".agentic/design_contracts")
CONTRACTS_FILE = "contracts.json"
MARKER_BEGIN = "<!-- PLATE-DESIGN-CONTRACT:BEGIN -->"
MARKER_END = "<!-- PLATE-DESIGN-CONTRACT:END -->"

STATUSES = ("draft", "pending_approval", "approved", "rejected", "superseded")


@dataclass
class DesignContract:
    """Visual/interaction contract bound to a Feature."""

    id: str
    feature_number: int | None
    feature_title: str
    status: str = "draft"
    version: int = 1
    visual_specs: list[str] = field(default_factory=list)
    interaction_criteria: list[str] = field(default_factory=list)
    a11y_criteria: list[str] = field(default_factory=list)
    artifact_paths: list[str] = field(default_factory=list)  # wireframes, mocks
    test_plan: list[str] = field(default_factory=list)
    approved_by: str | None = None
    approved_at: str | None = None
    created_at: str = ""
    updated_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DesignContract":
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _store_path(base: Path | None = None) -> Path:
    d = base or CONTRACTS_DIR
    if d.name == CONTRACTS_FILE:
        return d
    return d / CONTRACTS_FILE


def _load(base: Path | None = None) -> dict[str, Any]:
    path = _store_path(base)
    if not path.exists():
        return {"version": 1, "contracts": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"version": 1, "contracts": []}
        data.setdefault("version", 1)
        data.setdefault("contracts", [])
        if not isinstance(data["contracts"], list):
            data["contracts"] = []
        return data
    except (OSError, json.JSONDecodeError):
        return {"version": 1, "contracts": []}


def _save(data: dict[str, Any], base: Path | None = None) -> Path:
    path = _store_path(base)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return path


def render_contract_marker(payload: dict[str, Any]) -> str:
    return f"{MARKER_BEGIN}\n{json.dumps(payload, indent=2)}\n{MARKER_END}\n"


def default_a11y_criteria() -> list[str]:
    return [
        "Interactive controls are keyboard reachable",
        "Name, role, value exposed to assistive tech (axe clean critical)",
        "Color contrast meets WCAG AA for text",
    ]


def default_test_plan(*, has_playwright: bool = False) -> list[str]:
    plan = [
        "Unit: pure behavior for interaction criteria",
        "Contract: assert design contract criteria list is non-empty and approved before merge",
    ]
    if has_playwright:
        plan.extend(
            [
                "Playwright: happy-path interaction flow",
                "Playwright: axe accessibility scan on primary view",
                "Optional: visual snapshot / regression for primary state",
            ]
        )
    else:
        plan.append("Add Playwright (or equivalent) E2E when UI surface exists")
    return plan


def build_failing_test_scaffold(
    contract: dict[str, Any],
    *,
    language: str = "python",
) -> dict[str, Any]:
    """Generate failing-test scaffold text agents can drop into the repo (TDD)."""
    cid = contract.get("id") or "contract"
    title = contract.get("feature_title") or "feature"
    interactions = contract.get("interaction_criteria") or ["primary interaction works"]
    a11y = contract.get("a11y_criteria") or default_a11y_criteria()

    if language == "typescript":
        body = f'''// Design contract tests for {title} ({cid}) — #646
// Intentionally failing until implementation + Playwright wiring land.
import {{ test, expect }} from "@playwright/test";
// import AxeBuilder from "@axe-core/playwright";

test.describe("design contract: {title}", () => {{
  test.skip(!process.env.PLATE_E2E, "set PLATE_E2E=1 when e2e ready");

  test("interaction: {interactions[0][:60]}", async ({{ page }}) => {{
    await page.goto("/");
    // TODO: encode interaction criteria
    expect(false, "implement interaction for contract {cid}").toBeTruthy();
  }});

  test("a11y: no critical axe violations", async ({{ page }}) => {{
    await page.goto("/");
    // const results = await new AxeBuilder({{ page }}).analyze();
    // expect(results.violations.filter(v => v.impact === "critical")).toEqual([]);
    expect(false, "wire axe for contract {cid}").toBeTruthy();
  }});
}});
'''
        path_hint = f"tests/e2e/design_contract_{cid.replace('-', '_')}.spec.ts"
    else:
        # python unittest scaffold
        safe = re.sub(r"[^a-zA-Z0-9_]", "_", str(cid))
        criteria_repr = repr(list(interactions)[:5])
        a11y_repr = repr(list(a11y)[:5])
        body = f'''"""Design contract regression tests for {title} ({cid}) — #646.

Failing until implementation satisfies interaction + a11y criteria.
"""
from __future__ import annotations

import unittest


class TestDesignContract_{safe}(unittest.TestCase):
    CONTRACT_ID = "{cid}"
    INTERACTIONS = {criteria_repr}
    A11Y = {a11y_repr}

    def test_contract_is_approved(self):
        # Agents should replace with load of approved contract status
        self.fail(f"design contract {{self.CONTRACT_ID}} not yet validated as approved")

    def test_interaction_criteria_non_empty(self):
        self.assertTrue(self.INTERACTIONS, "interaction criteria required")

    def test_primary_interaction_placeholder(self):
        self.fail(
            f"implement primary interaction: {{self.INTERACTIONS[0] if self.INTERACTIONS else 'n/a'}}"
        )


if __name__ == "__main__":
    unittest.main()
'''
        path_hint = f"tests/test_design_contract_{safe}.py"

    return {
        "language": language,
        "path_hint": path_hint,
        "content": body,
        "contract_id": cid,
        "note": "Scaffold is intentionally failing (TDD). Do not weaken assertions to pass.",
    }


def propose_contract(
    *,
    feature_number: int | None = None,
    feature_title: str = "",
    visual_specs: list[str] | None = None,
    interaction_criteria: list[str] | None = None,
    a11y_criteria: list[str] | None = None,
    artifact_paths: list[str] | None = None,
    has_playwright: bool = False,
    submit_for_approval: bool = True,
    base_dir: Path | None = None,
) -> dict[str, Any]:
    """Create a design contract draft (optionally pending_approval)."""
    title = (feature_title or "").strip() or (
        f"Feature #{feature_number}" if feature_number else "Untitled feature"
    )
    interactions = list(interaction_criteria or [])
    if not interactions:
        interactions = [
            f"Primary user path for {title} completes successfully",
            "Error/empty states are reachable and understandable",
        ]
    visuals = list(visual_specs or [])
    if not visuals:
        visuals = [
            "Layout matches approved wireframe or written visual AC",
            "Primary CTA is visually dominant and labeled",
        ]
    a11y = list(a11y_criteria or default_a11y_criteria())
    ts = _now()
    contract = DesignContract(
        id=f"dc-{uuid.uuid4().hex[:10]}",
        feature_number=feature_number,
        feature_title=title,
        status="pending_approval" if submit_for_approval else "draft",
        version=1,
        visual_specs=visuals,
        interaction_criteria=interactions,
        a11y_criteria=a11y,
        artifact_paths=list(artifact_paths or []),
        test_plan=default_test_plan(has_playwright=has_playwright),
        created_at=ts,
        updated_at=ts,
        metadata={"has_playwright": has_playwright},
    )
    data = _load(base_dir)
    data["contracts"].append(contract.to_dict())
    _save(data, base_dir)
    scaffold = build_failing_test_scaffold(contract.to_dict())
    return {
        "ok": True,
        "contract": contract.to_dict(),
        "test_scaffold": scaffold,
        "marker": render_contract_marker(
            {"id": contract.id, "status": contract.status, "feature": feature_number}
        ),
        "ask_user_question": {
            "question": f"Approve design contract for {title}?",
            "options": [
                {
                    "id": "approve",
                    "label": "Approve contract",
                    "description": f"plate_design_contract_decide {contract.id} approve",
                },
                {
                    "id": "revise",
                    "label": "Request revisions",
                    "description": "Update visual/interaction criteria then re-propose",
                },
                {
                    "id": "reject",
                    "label": "Reject",
                    "description": f"plate_design_contract_decide {contract.id} reject",
                },
            ],
        },
    }


def list_contracts(
    *,
    status: str = "all",
    feature_number: int | None = None,
    limit: int = 50,
    base_dir: Path | None = None,
) -> list[dict[str, Any]]:
    out = []
    for c in _load(base_dir).get("contracts") or []:
        if status and status != "all" and c.get("status") != status:
            continue
        if feature_number is not None and c.get("feature_number") != feature_number:
            continue
        out.append(c)
    return out[: max(1, int(limit or 50))]


def get_contract(contract_id: str, *, base_dir: Path | None = None) -> dict[str, Any] | None:
    for c in _load(base_dir).get("contracts") or []:
        if c.get("id") == contract_id:
            return c
    return None


def decide_contract(
    contract_id: str,
    decision: str,
    *,
    decided_by: str = "human",
    note: str | None = None,
    base_dir: Path | None = None,
) -> dict[str, Any]:
    """approve | reject a pending design contract."""
    data = _load(base_dir)
    found = None
    for c in data["contracts"]:
        if c.get("id") == contract_id:
            found = c
            break
    if not found:
        return {"ok": False, "error": f"contract not found: {contract_id}"}
    dec = (decision or "").lower().strip()
    if dec not in ("approve", "approved", "reject", "rejected", "revise"):
        return {"ok": False, "error": f"invalid decision: {decision}"}
    if dec in ("approve", "approved"):
        found["status"] = "approved"
        found["approved_by"] = decided_by
        found["approved_at"] = _now()
    elif dec == "revise":
        found["status"] = "draft"
        found["version"] = int(found.get("version") or 1) + 1
    else:
        found["status"] = "rejected"
    if note:
        found.setdefault("metadata", {})
        found["metadata"]["decision_note"] = note
    found["updated_at"] = _now()
    _save(data, base_dir)
    return {"ok": True, "contract": found}


def update_contract(
    contract_id: str,
    *,
    visual_specs: list[str] | None = None,
    interaction_criteria: list[str] | None = None,
    a11y_criteria: list[str] | None = None,
    artifact_paths: list[str] | None = None,
    status: str | None = None,
    base_dir: Path | None = None,
) -> dict[str, Any]:
    data = _load(base_dir)
    found = None
    for c in data["contracts"]:
        if c.get("id") == contract_id:
            found = c
            break
    if not found:
        return {"ok": False, "error": f"contract not found: {contract_id}"}
    if visual_specs is not None:
        found["visual_specs"] = list(visual_specs)
    if interaction_criteria is not None:
        found["interaction_criteria"] = list(interaction_criteria)
    if a11y_criteria is not None:
        found["a11y_criteria"] = list(a11y_criteria)
    if artifact_paths is not None:
        found["artifact_paths"] = list(artifact_paths)
    if status:
        if status not in STATUSES:
            return {"ok": False, "error": f"invalid status: {status}"}
        found["status"] = status
    found["updated_at"] = _now()
    found["version"] = int(found.get("version") or 1) + 1
    _save(data, base_dir)
    return {"ok": True, "contract": found}


def validate_contract_readiness(
    contract_id: str | None = None,
    *,
    contract: dict[str, Any] | None = None,
    base_dir: Path | None = None,
) -> dict[str, Any]:
    """Check whether a contract is ready for autonomous feature implementation."""
    c = contract
    if contract_id and not c:
        c = get_contract(contract_id, base_dir=base_dir)
    if not c:
        return {"ok": False, "ready": False, "error": "contract required", "checks": []}
    checks = []
    def add(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": ok, "detail": detail})

    add("status_approved", c.get("status") == "approved", str(c.get("status")))
    add(
        "has_interaction_criteria",
        bool(c.get("interaction_criteria")),
        f"n={len(c.get('interaction_criteria') or [])}",
    )
    add(
        "has_visual_specs",
        bool(c.get("visual_specs")),
        f"n={len(c.get('visual_specs') or [])}",
    )
    add(
        "has_a11y_criteria",
        bool(c.get("a11y_criteria")),
        f"n={len(c.get('a11y_criteria') or [])}",
    )
    add("has_test_plan", bool(c.get("test_plan")), f"n={len(c.get('test_plan') or [])}")
    ready = all(x["ok"] for x in checks)
    return {
        "ok": True,
        "ready": ready,
        "contract_id": c.get("id"),
        "feature_number": c.get("feature_number"),
        "checks": checks,
        "scaffold": build_failing_test_scaffold(c) if ready or True else None,
    }


def contract_feed_items(
    *,
    limit: int = 10,
    base_dir: Path | None = None,
) -> list[dict[str, Any]]:
    items = []
    for c in list_contracts(status="pending_approval", limit=limit, base_dir=base_dir):
        items.append(
            {
                "id": c.get("id"),
                "item_type": "design_contract",
                "title": f"Design contract: {c.get('feature_title')}",
                "feature_number": c.get("feature_number"),
                "status": c.get("status"),
                "badges": ["design_contract", "pending_approval", "visual"],
                "source": "design_validation",
                "impact": "high",
                "reason": "Approve visual/interaction contract before Feature impl (#646)",
                "ask_user_question": {
                    "question": f"Approve design contract for {c.get('feature_title')}?",
                    "options": [
                        {
                            "id": "approve",
                            "label": "Approve",
                            "description": f"plate_design_contract_decide {c.get('id')} approve",
                        },
                        {
                            "id": "reject",
                            "label": "Reject",
                            "description": f"plate_design_contract_decide {c.get('id')} reject",
                        },
                    ],
                },
                "marker": render_contract_marker(
                    {"id": c.get("id"), "status": c.get("status")}
                ),
            }
        )
    return items
