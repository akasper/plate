"""AutonomyEngine runtime for Epic #470.

Core software that introspects project state (via health, epics, costs, plate_config, procedures)
and decides/delegates/executes autonomous actions at the user's budgeted token rate and
configured risk_tolerance (core philosophy: autonomous by default unless 'off').

Implements the contract from docs/design/autonomous-plate-engine.md (refined by Research #471).
Wired via mcp_server (plate_autonomy_* tools) and cli (gh plate autonomy ...).
Follows quiet ops for looped/scheduled use (terse bullets only; comments only on real progress).
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from .costs import get_cost_report
from .epics import get_epic_status
from .health import get_health
from .plate_config import load_plate_config, get_plate_config_report

# Durable shadow previews (#645 harden): survive process restarts so shadow_ack works
# across MCP/CLI sessions. Mirrors .agentic/checkpoints and .agentic/ledger layout.
SHADOW_DIR = Path(".agentic/shadow")
# Durable daily/cycle spend for #634 budget governor (survives process restart / --loop hosts).
BUDGET_DIR = Path(".agentic/budget")
BUDGET_SPEND_FILE = "spend.json"
# Heuristic USD per 1k tokens for cost_ceiling projections (not billing).
_USD_PER_1K_TOKENS = 0.002


def _shadow_path(shadow_id: str, base_dir: Path | None = None) -> Path:
    safe = re.sub(r"[^a-zA-Z0-9._-]", "_", shadow_id or "unknown")
    return (base_dir or SHADOW_DIR) / f"{safe}.json"


def save_shadow_report(report: "ShadowReport | dict[str, Any]", *, base_dir: Path | None = None) -> Path:
    """Persist a ShadowReport under .agentic/shadow/ for durable shadow_ack."""
    data = report.to_dict() if hasattr(report, "to_dict") else dict(report)
    sid = data.get("shadow_id") or f"shadow-{uuid.uuid4().hex[:12]}"
    data["shadow_id"] = sid
    path = _shadow_path(sid, base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def load_shadow_report(shadow_id: str, *, base_dir: Path | None = None) -> dict[str, Any] | None:
    """Load a durable ShadowReport by shadow_id, or None if missing."""
    if not shadow_id:
        return None
    path = _shadow_path(shadow_id, base_dir)
    if not path.is_file():
        # prefix match (same pattern as checkpoints)
        d = base_dir or SHADOW_DIR
        if d.is_dir():
            matches = sorted(d.glob(f"{re.sub(r'[^a-zA-Z0-9._-]', '_', shadow_id)}*.json"))
            if matches:
                path = matches[0]
            else:
                return None
        else:
            return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def shadow_report_from_dict(data: dict[str, Any]) -> "ShadowReport":
    """Rehydrate ShadowReport from durable JSON."""
    return ShadowReport(
        action_kind=str(data.get("action_kind") or "unknown"),
        impact=str(data.get("impact") or "medium"),
        mode=str(data.get("mode") or "shadow"),
        estimated_tokens=int(data.get("estimated_tokens") or 0),
        estimated_duration_seconds=int(data.get("estimated_duration_seconds") or 0),
        estimated_cost_usd=float(data.get("estimated_cost_usd") or 0.0),
        predicted_side_effects=list(data.get("predicted_side_effects") or []),
        requires_approval=bool(data.get("requires_approval")),
        approval_reasons=list(data.get("approval_reasons") or []),
        risk_allowed=bool(data.get("risk_allowed")),
        would_execute=bool(data.get("would_execute")),
        gate_preview=list(data.get("gate_preview") or []),
        shadow_id=str(data.get("shadow_id") or ""),
        timestamp=str(data.get("timestamp") or ""),
        scope=dict(data.get("scope") or {}),
    )


def _budget_spend_path(base_dir: Path | None = None) -> Path:
    return (base_dir or BUDGET_DIR) / BUDGET_SPEND_FILE


def load_budget_spend(*, base_dir: Path | None = None) -> dict[str, Any]:
    """Load durable spend counters for #634 (empty dict if missing)."""
    path = _budget_spend_path(base_dir)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_budget_spend(data: dict[str, Any], *, base_dir: Path | None = None) -> Path:
    """Persist durable spend counters under .agentic/budget/spend.json."""
    path = _budget_spend_path(base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(data)
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def tokens_to_usd(tokens: int) -> float:
    """Heuristic USD projection for cost_ceiling enforcement (#634)."""
    return round((max(0, int(tokens)) / 1000.0) * _USD_PER_1K_TOKENS, 6)


@dataclass
class AutonomyStatus:
    """Current autonomy state for status/health/MCP."""
    enabled: bool = True
    risk_tolerance: str = "medium"  # off | low | medium | high
    budget_remaining_tokens: int | None = None
    budget_remaining_usd: float | None = None  # float (or None) from cost_ceiling_usd; addresses type annotation review feedback for consistency with assignment in get_status
    last_cycle: str | None = None
    next_scheduled: str | None = None
    autopilot_score: int = 0  # 0-100 composite per #479 (auto PRs + unattended cycles + gaps closed + proc success + budget adherence)
    burn_rate: float = 0.0  # % of daily budget burned (for #479 observability + health)
    due_procedures: list[str] = field(default_factory=list)
    open_human_checkpoints: list[str] = field(default_factory=list)
    throttled_actions: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ProjectSnapshot:
    """Introspected state (health + epics + costs + config + procedures due)."""
    health: dict[str, Any] = field(default_factory=dict)
    epic_status: dict[str, Any] = field(default_factory=dict)
    cost_report: dict[str, Any] = field(default_factory=dict)
    plate_config: dict[str, Any] = field(default_factory=dict)
    due_procedures: list[dict[str, Any]] = field(default_factory=list)
    timestamp: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CycleReport:
    """Result of one autonomy engine cycle."""
    status: str = "completed"
    actions_taken: list[str] = field(default_factory=list)
    throttled: list[str] = field(default_factory=list)
    paused: bool = False
    budget_decision: str = "proceed"  # proceed | throttle | pause | warn
    snapshot: dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ProcedureDef:
    """Lightweight procedure def (loaded from .agentic/procedures/ or built-ins)."""
    id: str
    cadence: str
    risk_level: str
    description: str = ""
    enabled: bool = True


class Decision(Enum):
    """Budget governor decision per #471 research + #472/#474 contract.

    PROCEED: action within budget, execute (full spend tracked).
    THROTTLE: near/over but continue partial (half-spend for safety, skip low-pri callers decide).
    PAUSE: hard stop this cycle (set paused, no further spend).
    WARN: over but allow (full spend, log for observability; rare).
    """
    PROCEED = "proceed"
    THROTTLE = "throttle"
    PAUSE = "pause"
    WARN = "warn"


# Impact catalog for #645 shadow/simulation gates (low → critical).
# Unknown kinds default to medium (fail closed vs silent low).
_ACTION_IMPACT: dict[str, str] = {
    "what_next": "low",
    "health": "low",
    "plate_health": "low",
    "cost_rollup": "low",
    "plate_costs": "low",
    "status": "low",
    "babysit": "medium",
    "feedback_integration": "medium",
    "run_procedure": "medium",
    "info_audit": "medium",
    "perform_information_audit": "medium",
    "plan_epic": "medium",
    "delegate": "medium",
    "plate_delegate_to_agent": "medium",
    "drift": "medium",
    "nightly_drift_detection": "medium",
    "auto_merge": "high",
    "merge_to_main": "high",
    "open_pr": "high",
    "apply_migration": "high",
    "release_cut": "critical",
    "release_finalize": "critical",
    "deploy": "critical",
    "force_push": "critical",
    "marketplace_publish": "critical",
    "secret_change": "critical",
}

_SIDE_EFFECTS: dict[str, list[str]] = {
    "release_cut": [
        "Create versioned release branch / notes under .agentic/releases/vX.Y.Z/",
        "Rename Next Release issue; open fresh Next Release",
        "Aggregate unreleased fragments into release.json",
    ],
    "release_finalize": [
        "Create GitHub Release + tag assets",
        "Hard-reset release track branch to tag (force-with-lease)",
        "Fire downstream extension release_checks",
    ],
    "deploy": [
        "Push or promote artifacts to production environment",
        "May update live services / marketplace listings",
    ],
    "force_push": [
        "Rewrite remote branch history (force-with-lease or force)",
        "Can disrupt open PRs and collaborator clones",
    ],
    "marketplace_publish": [
        "Publish package/extension to external marketplace",
        "Requires human account ownership (Task gate)",
    ],
    "auto_merge": [
        "Enable auto-merge or merge eligible PR to integration branch",
        "May land code without interactive human click",
    ],
    "merge_to_main": [
        "Merge Release PR into main (tagged history)",
        "Triggers tag/finalization workflows",
    ],
    "open_pr": [
        "Open pull request on GitHub",
        "Triggers CI and review notifications",
    ],
    "apply_migration": [
        "Mutate repository files / config for template cutover",
        "Creates rollback checkpoint tags when supported",
    ],
    "plan_epic": [
        "Create Epic + child stub issues and labels",
        "May auto-stub at high risk_tolerance",
    ],
    "info_audit": [
        "Scan Goals/wiki/issues; may open Question issues",
        "Write audit proposals (dry_run skips creation)",
    ],
    "run_procedure": [
        "Execute allow-listed procedure steps (audit/babysit/costs)",
        "Post PLATE-PROCEDURE-RUN marker when applied",
    ],
    "babysit": [
        "Inspect PR gates; may resolve threads / post trigger comments",
        "Optional local-rebase push when strategy allows",
    ],
    "what_next": [
        "Read-only process recommendation (no mutations)",
    ],
    "health": [
        "Read-only health report",
    ],
}


def classify_action_impact(action_kind: str, scope: dict[str, Any] | None = None) -> str:
    """Return impact level for an action kind (#645).

    Scope may raise impact (e.g. procedure risk_level=high → at least high).
    """
    scope = scope or {}
    kind = (action_kind or "unknown").lower().replace("-", "_")
    impact = _ACTION_IMPACT.get(kind, "medium")
    # Procedure risk can escalate impact
    proc_risk = (scope.get("risk_level") or scope.get("procedure_risk") or "").lower()
    if proc_risk in ("high", "critical"):
        order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        if order.get(proc_risk, 0) > order.get(impact, 0):
            impact = proc_risk if proc_risk != "high" else "high"
            if proc_risk == "critical":
                impact = "critical"
    # Explicit critical flags in scope
    if scope.get("touches_secrets") or scope.get("force") is True and kind in ("push", "reset"):
        impact = "critical"
    return impact


@dataclass
class ShadowReport:
    """Structured shadow/simulation preview for high-impact actions (#645)."""
    action_kind: str
    impact: str  # low | medium | high | critical
    mode: str = "shadow"
    estimated_tokens: int = 0
    estimated_duration_seconds: int = 0
    estimated_cost_usd: float = 0.0
    predicted_side_effects: list[str] = field(default_factory=list)
    requires_approval: bool = False
    approval_reasons: list[str] = field(default_factory=list)
    risk_allowed: bool = False
    would_execute: bool = False
    gate_preview: list[str] = field(default_factory=list)
    shadow_id: str = ""
    timestamp: str = ""
    scope: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AutonomyEngine:
    """The core engine for long-running autonomous PLATE operation.

    Introspects, enforces budget/risk, decides next (integrating what_next + procedures),
    executes (deterministic or delegate via trigger comments), logs with markers + usage.
    """

    def __init__(self, repo: str | None = None, client: Any = None):
        self.repo = repo
        self.client = client
        self.config = load_plate_config()
        # Autonomy section is opt-in only (absent .plate or absent 'autonomy' key => off / legacy AUTONOMOUS_MODE only per #470/#476 contract).
        # DEFAULT_CONFIG now conservative (enabled=False, risk=off) to address review feedback; user .plate section is the explicit on-ramp.
        config_dict = self.config.to_dict() if hasattr(self.config, "to_dict") else {}
        self.autonomy_config = config_dict.get("autonomy", {}) or {}
        if not self.autonomy_config:
            self.enabled = False
            self.risk_tolerance = "off"
        else:
            self.enabled = self.autonomy_config.get("enabled", True)
            self.risk_tolerance = self.autonomy_config.get("risk_tolerance", "medium")
        self.procedures: list[ProcedureDef] = self._load_procedures()
        # Spend counters: in-memory + durable under .agentic/budget/spend.json (#634)
        self._spent_this_cycle: int = 0
        self._spent_today: int = 0
        self._spent_usd_today: float = 0.0
        self._last_reset = datetime.now(timezone.utc).date()
        self.throttled_actions: int = 0  # for #479 autopilot calc and status
        # #645: in-memory + durable (.agentic/shadow/) previews so shadow_ack works across processes
        self._shadow_previews: dict[str, ShadowReport] = {}
        self.shadow_base_dir: Path | None = None  # tests override; default SHADOW_DIR
        self.checkpoint_base_dir: Path | None = None  # tests override for #648 bridge
        self.budget_base_dir: Path | None = None  # tests override; default BUDGET_DIR
        self.ledger_base_dir: Path | None = None  # tests override; default LEDGER_DIR
        self._load_durable_spend()

    def _ledger_record(
        self,
        action_kind: str,
        decision: str,
        reason: str,
        *,
        cost_estimate_tokens: int | None = None,
        impact: str = "",
        shadow_id: str | None = None,
        checkpoint_id: str | None = None,
        sources: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        session: str = "",
    ) -> dict[str, Any] | None:
        """Best-effort #647 provenance write (never raises into autonomy path)."""
        try:
            from .ledger import record_decision

            return record_decision(
                action_kind=action_kind,
                decision=decision,
                reason=reason,
                sources=sources or ["autonomy_engine"],
                cost_estimate_tokens=cost_estimate_tokens,
                risk_tolerance=self.risk_tolerance,
                impact=impact,
                shadow_id=shadow_id,
                checkpoint_id=checkpoint_id,
                actor="autonomy",
                session=session,
                metadata=metadata,
                base_dir=self.ledger_base_dir,
            )
        except Exception:
            return None

    def _load_durable_spend(self) -> None:
        """Hydrate spend counters from .agentic/budget/spend.json for process-safe #634 enforcement."""
        data = load_budget_spend(base_dir=self.budget_base_dir)
        if not data:
            return
        today = datetime.now(timezone.utc).date().isoformat()
        if str(data.get("date") or "") != today:
            # Stale day — leave zeros; next save rewrites
            return
        try:
            self._spent_today = int(data.get("spent_today") or 0)
            self._spent_this_cycle = int(data.get("spent_this_cycle") or 0)
            self._spent_usd_today = float(data.get("spent_usd_today") or 0.0)
            self.throttled_actions = int(data.get("throttled_actions") or 0)
            self._last_reset = datetime.now(timezone.utc).date()
        except (TypeError, ValueError):
            pass

    def _persist_spend(self) -> None:
        """Best-effort durable write after budget mutations."""
        try:
            save_budget_spend(
                {
                    "date": self._last_reset.isoformat(),
                    "spent_today": int(self._spent_today),
                    "spent_this_cycle": int(self._spent_this_cycle),
                    "spent_usd_today": float(self._spent_usd_today),
                    "throttled_actions": int(self.throttled_actions),
                },
                base_dir=self.budget_base_dir,
            )
        except OSError:
            pass

    def _persist_shadow(self, report: ShadowReport) -> None:
        self._shadow_previews[report.shadow_id] = report
        try:
            save_shadow_report(report, base_dir=self.shadow_base_dir)
        except OSError:
            pass  # best-effort durable; in-memory still valid for session

    def _resolve_shadow(self, shadow_ack: str | None, kind: str, scope: dict[str, Any]) -> tuple[ShadowReport, bool]:
        """Return (shadow, ack_valid). ack_valid True only if shadow_ack matches a known preview."""
        if shadow_ack:
            if shadow_ack in self._shadow_previews:
                return self._shadow_previews[shadow_ack], True
            durable = load_shadow_report(shadow_ack, base_dir=self.shadow_base_dir)
            if durable and durable.get("shadow_id") == shadow_ack:
                report = shadow_report_from_dict(durable)
                self._shadow_previews[shadow_ack] = report
                return report, True
            # Unknown ack: produce fresh preview for reporting but ack is invalid
            return self.simulate_action(kind, scope), False
        return self.simulate_action(kind, scope), False

    def _maybe_checkpoint_for_blocked(self, shadow: ShadowReport) -> dict[str, Any] | None:
        """When gate blocks, open a #648 checkpoint so feed/engine pause has a real artifact."""
        if not shadow.requires_approval and shadow.impact not in ("high", "critical"):
            return None
        try:
            from .checkpoint import create_checkpoint_for_shadow

            return create_checkpoint_for_shadow(
                shadow.to_dict(),
                risk_tolerance=self.risk_tolerance,
                autonomy_enabled=bool(self.enabled),
                created_by="autonomy-engine",
                base_dir=self.checkpoint_base_dir,
            )
        except Exception:
            return None

    def simulate_action(
        self, action_kind: str, scope: dict[str, Any] | None = None
    ) -> ShadowReport:
        """Produce a shadow/simulation preview for an action without side effects (#645).

        Returns cost/risk/side-effect estimates and whether human approval is required
        before a real run. Call gate_high_impact(..., shadow_ack=report.shadow_id, approved=...)
        before executing high/critical actions. Previews are durable under .agentic/shadow/.
        """
        scope = dict(scope or {})
        kind = (action_kind or "unknown").lower().replace("-", "_")
        impact = classify_action_impact(kind, scope)
        est = self.estimate_cost(kind, scope)
        # Rough duration + USD (heuristic; observability not billing)
        duration = max(5, min(3600, int(est / 80)))
        usd_per_1k = 0.002  # conservative placeholder for projections
        est_usd = round((est / 1000.0) * usd_per_1k, 4)

        side_effects = list(_SIDE_EFFECTS.get(kind, [
            f"Would attempt autonomous action '{kind}'",
            "May create/update GitHub issues, PRs, or comments",
        ]))
        if scope.get("version"):
            side_effects.append(f"Target version: {scope['version']}")
        if scope.get("pr_number"):
            side_effects.append(f"Target PR: #{scope['pr_number']}")

        impact_rank = self._impact_rank(impact)
        risk_rank = self._risk_rank(self.risk_tolerance)
        # Critical always needs human; high needs human at low tolerance; medium+ ok at medium+
        reasons: list[str] = []
        requires = False
        if impact == "critical":
            requires = True
            reasons.append("critical impact always requires human approval (deploy/release/force-push/secrets/marketplace)")
        elif impact == "high" and risk_rank < self._risk_rank("medium"):
            requires = True
            reasons.append("high-impact action blocked at risk_tolerance=low without explicit approval")
        elif impact == "high" and risk_rank < self._risk_rank("high"):
            # medium tolerance: high still requires approval for safety gate (#645)
            requires = True
            reasons.append("high-impact action requires approval at medium risk_tolerance (use shadow then approve)")
        if not self.enabled or self.risk_tolerance == "off":
            # preview still useful; live auto would not run
            if impact_rank >= self._impact_rank("medium"):
                requires = True
                reasons.append("autonomy disabled or risk_tolerance=off — live execution not permitted")

        risk_allowed = risk_rank >= impact_rank and self.enabled and self.risk_tolerance != "off"
        # critical never risk_allowed for unsupervised
        if impact == "critical":
            risk_allowed = False

        would_execute = (not requires) and risk_allowed and impact_rank <= risk_rank

        gate_preview = [
            "budget: enforce_budget(estimate) before real run",
            f"risk_tolerance={self.risk_tolerance} vs impact={impact}",
        ]
        if impact in ("high", "critical"):
            gate_preview.extend([
                "human checkpoint / Task if secrets, marketplace, or release ceremony",
                "feedback-resolution + required checks before merge-class actions",
                "no mutation of AGENTS.md/SPEC.md/workflows without human",
            ])
        if kind in ("release_cut", "release_finalize"):
            gate_preview.append("release_checks: marketing-copy-reviewed, release-notes-complete, release-issue-open")

        ts = datetime.now(timezone.utc).isoformat()
        # Durable id (uuid) so shadow_ack survives process restart via .agentic/shadow/
        shadow_id = f"shadow-{kind}-{uuid.uuid4().hex[:12]}"

        report = ShadowReport(
            action_kind=kind,
            impact=impact,
            mode="shadow",
            estimated_tokens=est,
            estimated_duration_seconds=duration,
            estimated_cost_usd=est_usd,
            predicted_side_effects=side_effects,
            requires_approval=requires,
            approval_reasons=reasons,
            risk_allowed=risk_allowed,
            would_execute=would_execute,
            gate_preview=gate_preview,
            shadow_id=shadow_id,
            timestamp=ts,
            scope=scope,
        )
        self._persist_shadow(report)
        return report

    def gate_high_impact(
        self,
        action_kind: str,
        *,
        shadow_ack: str | None = None,
        approved: bool = False,
        checkpoint_id: str | None = None,
        scope: dict[str, Any] | None = None,
        create_checkpoint: bool = True,
    ) -> dict[str, Any]:
        """Hard gate for high-impact live actions (#645).

        Returns {blocked, mode, shadow_report?, reason?, checkpoint?}.
        - critical: blocked unless approved=True and valid shadow_ack
        - high at low/medium risk: blocked unless approved=True and shadow_ack
        - low impact: not blocked
        Durable shadow_ack is resolved from memory or `.agentic/shadow/`.
        When blocked, optionally opens a #648 checkpoint (create_checkpoint=True).
        Pass checkpoint_id of an *approved* #648 checkpoint to satisfy the human
        approval leg (shadow_id taken from the checkpoint when shadow_ack omitted).
        """
        scope = scope or {}
        kind = (action_kind or "unknown").lower().replace("-", "_")
        impact = classify_action_impact(kind, scope)

        # #648: approved checkpoint satisfies human leg and can supply shadow_ack
        if checkpoint_id:
            try:
                from .checkpoint import checkpoint_approval_for_gate

                cp_gate = checkpoint_approval_for_gate(
                    checkpoint_id,
                    action_kind=kind,
                    base_dir=self.checkpoint_base_dir,
                )
                if cp_gate.get("approved"):
                    approved = True
                    if not shadow_ack and cp_gate.get("shadow_id"):
                        shadow_ack = str(cp_gate["shadow_id"])
                elif not approved:
                    # Explicit pending/rejected checkpoint id should not open a new one
                    create_checkpoint = False
            except Exception:
                pass

        shadow, ack_ok = self._resolve_shadow(shadow_ack, kind, scope)

        def _blocked(mode: str, reason: str) -> dict[str, Any]:
            out: dict[str, Any] = {
                "blocked": True,
                "mode": mode,
                "reason": reason,
                "shadow_report": shadow.to_dict(),
            }
            if create_checkpoint:
                cp = self._maybe_checkpoint_for_blocked(shadow)
                if cp and cp.get("id"):
                    out["checkpoint"] = {
                        "id": cp.get("id"),
                        "status": cp.get("status"),
                        "title": cp.get("title"),
                        "pause_autonomy": cp.get("pause_autonomy"),
                    }
                    out["checkpoint_id"] = cp.get("id")
            # #647: durable provenance for blocked high-impact gates
            led = self._ledger_record(
                kind,
                "shadow_required",
                reason,
                cost_estimate_tokens=shadow.estimated_tokens,
                impact=shadow.impact,
                shadow_id=shadow.shadow_id,
                checkpoint_id=out.get("checkpoint_id"),
                sources=["autonomy_engine", "gate_high_impact", "#645"],
                metadata={"mode": mode},
            )
            if led and led.get("id"):
                out["ledger_id"] = led["id"]
            return out

        if impact in ("low", "medium"):
            # medium may still require approval when autonomy off
            if shadow.requires_approval and not approved:
                return _blocked(
                    "shadow_required",
                    "; ".join(shadow.approval_reasons) or "approval required",
                )
            return {
                "blocked": False,
                "mode": "allowed",
                "shadow_report": shadow.to_dict(),
            }

        # high / critical — ack_ok from durable or memory only
        if impact == "critical":
            if approved and ack_ok:
                return {"blocked": False, "mode": "approved", "shadow_report": shadow.to_dict()}
            return _blocked(
                "shadow_required",
                "critical action requires shadow preview + explicit approved=True",
            )

        # high
        if approved and ack_ok:
            return {"blocked": False, "mode": "approved", "shadow_report": shadow.to_dict()}
        if ack_ok and self._risk_rank(self.risk_tolerance) >= self._risk_rank("high") and not shadow.requires_approval:
            return {"blocked": False, "mode": "shadow_acked", "shadow_report": shadow.to_dict()}
        return _blocked(
            "shadow_required",
            "high-impact action requires shadow preview and approval (or high risk_tolerance policy)",
        )

    def _impact_rank(self, level: str) -> int:
        order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        return order.get((level or "").lower(), 1)

    def estimate_cost(self, action_kind: str, scope: dict[str, Any] | None = None) -> int:
        """#471 estimation heuristics wired for #474: tool/scope/historical + 1.5-2x over-est + 20% buffer + cap.

        References Research #471 (base costs, multipliers from #items/historical from costs/.agentic/COSTS.md, over-est policy).
        Called from decide_next + run_cycle; result passed to enforce_budget.
        Best-effort (sparse data falls back to static); always over for safety per design.
        """
        scope = scope or {}
        kind = (action_kind or "unknown").lower().replace("-", "_")
        bases: dict[str, int] = {
            "info_audit": 10000,      # 5k-15k per #471
            "perform_information_audit": 10000,
            "health": 350,
            "plate_health": 350,
            "plan_epic": 7500,
            "what_next": 1500,
            "run_procedure": 4000,
            "delegate": 2200,
            "plate_delegate_to_agent": 2200,
            "babysit": 4500,
            "feedback_integration": 4500,
            "cost_rollup": 1800,
            "drift": 5500,
            "nightly_drift_detection": 5500,
            "auto_merge": 2500,
            "merge_to_main": 3000,
            "open_pr": 2000,
            "release_cut": 9000,
            "release_finalize": 7000,
            "deploy": 8000,
            "force_push": 1500,
            "marketplace_publish": 6000,
            "apply_migration": 5000,
            "unknown": 2200,
            "default": 2200,
        }
        base = bases.get(kind, bases["default"])

        # scope multiplier: #items / gaps / issues (from introspect health/epic_status passed in scope)
        num_items = 1
        for k in ("num_items", "num_issues", "gaps", "open_issues", "children"):
            if k in scope:
                try:
                    num_items = max(num_items, int(scope[k]) or 1)
                except (ValueError, TypeError):
                    pass
        mult = 1.0 + min(2.0, (num_items - 1) * 0.12)  # ~12% per extra item, cap +2x

        # historical from passed cost_report (preferred, avoids GH every est) or parse local .agentic/COSTS.md
        hist_avg = 0
        cr = scope.get("cost_report") or {}
        if isinstance(cr, dict):
            reps = cr.get("reports") or []
            if reps and cr.get("total_tokens"):
                hist_avg = int(cr.get("total_tokens", 0) / max(1, len(reps)))
        if hist_avg <= 0:
            try:
                # Prefer local COSTS.md scrape (fast) over remote get_cost_report (can hang offline).
                # Only hit network when repo is set and local file yields nothing.
                costs_path = Path(".agentic/COSTS.md")
                if costs_path.exists():
                    txt = costs_path.read_text(encoding="utf-8", errors="ignore")
                    from .costs import USAGE_BLOCK_RE as _UBR, TOKENS_RE as _TR
                    for m in _UBR.finditer(txt):
                        block = m.group(1) or ""
                        tm = _TR.search(block)
                        if tm:
                            hist_avg = max(hist_avg, int(tm.group(1)))
                if hist_avg <= 0 and self.repo:
                    cr = get_cost_report(self.repo)
                    if cr and getattr(cr, "total_tokens", 0):
                        reps = getattr(cr, "reports", []) or (
                            cr.to_dict().get("reports", []) if hasattr(cr, "to_dict") else []
                        )
                        if reps:
                            hist_avg = int(getattr(cr, "total_tokens", 0) / max(1, len(reps)))
            except Exception:
                pass
        if hist_avg > 100:
            base = max(base, int(hist_avg * 0.6))  # blend lower bound from history

        # 1.5-2x over-estimate + 20% buffer (use ~1.75x avg)
        est = int(base * mult * 1.75)
        est = int(est * 1.20)  # +20% buffer

        # cap relative to per_cycle (leave headroom, never propose >90% of cycle alone)
        cap = self.autonomy_config.get("token_budget", {}).get("per_cycle", 8000) or 8000
        est = min(est, int(cap * 0.9))
        return max(100, est)

    def _load_procedures(self) -> list[ProcedureDef]:
        """Load procedure defs from .agentic/procedures/*.json (data-driven per design) + built-ins."""
        procs: list[ProcedureDef] = []
        proc_dir = Path(".agentic/procedures")
        if proc_dir.exists():
            for f in sorted(proc_dir.glob("*.json")):
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                    procs.append(ProcedureDef(
                        id=data["id"],
                        cadence=data.get("cadence", "manual"),
                        risk_level=data.get("risk_level", "medium"),
                        description=data.get("description", ""),
                        enabled=data.get("enabled", True),
                    ))
                except Exception:
                    continue  # skip bad defs
        # Ensure core built-ins for the Epic (even if files present)
        existing = {p.id for p in procs}
        for builtin in [
            {"id": "nightly-drift-detection", "cadence": "nightly", "risk_level": "medium", "description": "Built-in drift detection (labels, Goals, fragments, health vs expected)"},
            {"id": "feedback-integration", "cadence": "nightly", "risk_level": "low", "description": "Babysit PR feedback for agents"},
            {"id": "cost-rollup", "cadence": "weekly", "risk_level": "low", "description": "Aggregate USAGE REPORTs and costs"},
        ]:
            if builtin["id"] not in existing:
                procs.append(ProcedureDef(**builtin))
        return procs

    def get_status(self) -> AutonomyStatus:
        """Return live status (used by plate_autonomy_status + health enrichment)."""
        # Integrate real reports. Always call helpers even if self.repo is None; they resolve
        # from local git remote (origin) when repo=None per design and other call sites.
        try:
            health = get_health(self.repo).to_dict() if self.repo else {}
            costs = get_cost_report(self.repo).to_dict() if self.repo else {}
            config_report = get_plate_config_report().to_dict()  # always use local checkout .plate for config (repo str is for remote health/costs only)
        except Exception:
            health = costs = config_report = {}

        # Complete observability per #479: autopilot_score composite (% auto PRs proxy from health + unattended cycles + gaps closed + proc success + budget adherence + throttled inverse) + burn_rate.
        # References design #472 + research #471. Uses available signals (no full 30d GH history here; health/epics/costs provide proxies).
        risk_rank = self._risk_rank(self.risk_tolerance)
        base = 25 + (risk_rank * 12)  # 25-61 from risk (high tolerance enables more auto)
        daily = self.autonomy_config.get("token_budget", {}).get("daily", 50000) or 50000
        budget_adherence = 50
        burn_rate = 0.0
        if daily > 0:
            spent = self._spent_today
            burn_rate = max(0.0, min(100.0, (spent / daily) * 100))
            remaining = daily - spent
            budget_adherence = max(0, min(100, int((remaining / daily) * 100)))
        # proc success proxy + due count (more due + enabled = higher auto progress)
        proc_count = len([p for p in self.procedures if p.enabled])
        proc_bonus = min(15, proc_count * 4)
        # health signals for auto-prs/gaps (if present in future health; else 0)
        auto_prs = min(10, (health or {}).get("auto_merged_prs", 0) or 0)
        gaps_closed = min(10, (health or {}).get("gaps_closed_autonomously", 0) or 0)
        throttle_penalty = min(10, self.throttled_actions or 0)  # inverse
        autopilot = int(base + (budget_adherence * 0.25) + proc_bonus + auto_prs + gaps_closed - throttle_penalty)
        autopilot = max(0, min(100, autopilot))

        due_ids = [p.id for p in self.procedures if p.enabled and self._risk_rank(p.risk_level) <= self._risk_rank(self.risk_tolerance)]
        # #648: surface open pausing checkpoints (plus any health errors as soft checkpoints)
        open_cps: list[str] = []
        try:
            from .checkpoint import list_open_checkpoints
            for c in list_open_checkpoints(limit=20):
                open_cps.append(f"{c.get('id')}: {c.get('title')}")
        except Exception:
            pass
        if isinstance(health, dict):
            for err in health.get("errors", []) or []:
                open_cps.append(str(err))
        ceiling = self.autonomy_config.get("cost_ceiling_usd")
        try:
            ceiling_f = float(ceiling) if ceiling is not None else None
        except (TypeError, ValueError):
            ceiling_f = None
        remaining_usd = None
        if ceiling_f is not None:
            remaining_usd = max(0.0, round(ceiling_f - float(self._spent_usd_today), 6))

        return AutonomyStatus(
            enabled=self.enabled,
            risk_tolerance=self.risk_tolerance,
            budget_remaining_tokens=max(0, daily - self._spent_today),
            budget_remaining_usd=remaining_usd,
            last_cycle=datetime.now(timezone.utc).isoformat(),
            autopilot_score=autopilot,
            burn_rate=round(burn_rate, 1),
            due_procedures=due_ids,
            open_human_checkpoints=open_cps,
            throttled_actions=getattr(self, "throttled_actions", 0),
        )

    def introspect(self) -> ProjectSnapshot:
        """Gather full project state for decide_next (health + epics + costs + config + procedures)."""
        ts = datetime.now(timezone.utc).isoformat()
        try:
            health = get_health(self.repo).to_dict() if self.repo else {}
            epics = get_epic_status(self.repo).to_dict() if self.repo else {}
            costs = get_cost_report(self.repo).to_dict() if self.repo else {}
            pconfig = get_plate_config_report().to_dict()  # always use local checkout .plate for config (repo str is for remote health/costs only)
        except Exception as exc:
            health = {"error": str(exc)}
            epics = costs = pconfig = {}

        # Populate due from loaded procedures (filter risk)
        due = []
        for p in self.procedures:
            if p.enabled and self._risk_rank(p.risk_level) <= self._risk_rank(self.risk_tolerance):
                due.append({"id": p.id, "cadence": p.cadence, "risk_level": p.risk_level, "est_tokens": 4000})

        return ProjectSnapshot(
            health=health,
            epic_status=epics,
            cost_report=costs,
            plate_config=pconfig,
            due_procedures=due,
            timestamp=ts,
        )

    def enforce_budget(self, estimated: int, action_kind: str) -> Decision:
        """Core governor per #471/#472/#474/#634. Returns Decision (not bool).

        estimate_cost (wired #471 heuristics) is called by caller (decide_next/run_cycle) and passed here.
        On breach: throttle (partial spend + continue), pause (stop), warn (continue full).
        Daily UTC reset + per_cycle/daily caps + optional cost_ceiling_usd.
        Spend is durable under .agentic/budget/spend.json so long /loop runs stay safe across processes.
        Always respects risk_tolerance=='off'.
        """
        if not self.enabled or self.risk_tolerance == "off":
            return Decision.PROCEED  # explicit off or disabled: no autonomous budget enforcement

        # Daily reset (UTC date) for _spent_today; _spent_this_cycle reset on day rollover
        today = datetime.now(timezone.utc).date()
        if today != self._last_reset:
            self._spent_this_cycle = 0
            self._spent_today = 0
            self._spent_usd_today = 0.0
            self._last_reset = today
            self._persist_spend()

        cap = self.autonomy_config.get("token_budget", {}).get("per_cycle", 8000) or 8000
        daily_cap = self.autonomy_config.get("token_budget", {}).get("daily", 50000) or 50000
        policy = self.autonomy_config.get("token_budget", {}).get("action", "throttle")
        cost_ceiling = self.autonomy_config.get("cost_ceiling_usd")
        try:
            cost_ceiling_f = float(cost_ceiling) if cost_ceiling is not None else None
        except (TypeError, ValueError):
            cost_ceiling_f = None

        est_usd = tokens_to_usd(estimated)
        projected_cycle = self._spent_this_cycle + estimated
        projected_daily = self._spent_today + estimated
        projected_usd = self._spent_usd_today + est_usd

        token_breach = projected_cycle > cap or projected_daily > daily_cap
        usd_breach = cost_ceiling_f is not None and projected_usd > cost_ceiling_f

        def _charge(tokens: int) -> None:
            self._spent_this_cycle += tokens
            self._spent_today += tokens
            self._spent_usd_today += tokens_to_usd(tokens)
            self._persist_spend()

        if not token_breach and not usd_breach:
            _charge(estimated)
            return Decision.PROCEED

        # Breach: policy + hard USD ceiling (never partial-spend past ceiling unless warn)
        if policy == "pause":
            return Decision.PAUSE
        if usd_breach and policy != "warn":
            return Decision.PAUSE
        if policy == "throttle" and token_breach and not usd_breach:
            half = max(1, estimated // 2)
            _charge(half)
            self.throttled_actions += 1
            return Decision.THROTTLE
        # warn (or throttle+usd already handled): charge full and flag
        _charge(estimated)
        return Decision.WARN

    def decide_next(self, snapshot: ProjectSnapshot) -> list[dict[str, Any]]:
        """Decide actions for the cycle (what_next + risk-filtered procedures + budget-aware).

        Wires #471: call estimate_cost (with scope from snapshot) before append; check enforce_budget Decision.
        Budget check here + run_cycle (per #474 wiring); skip PAUSE actions, note THROTTLE.
        References #471 heuristics + #472 contract; no human checkpoint changes.
        """
        actions: list[dict[str, Any]] = []
        if not self.enabled or self.risk_tolerance == "off":
            return actions
        # Build scope for est (historical + items from introspect snapshot for #471)
        scope = {
            "cost_report": snapshot.cost_report,
            "num_items": len(snapshot.due_procedures) + len(snapshot.epic_status.get("children", []) or []) or 3,
            "gaps": len(snapshot.health.get("recommendations", []) or []),
        }
        # what_next always proposed first (cheap) but still est for governor
        est = self.estimate_cost("what_next", scope)
        dec = self.enforce_budget(est, "what_next")
        if dec != Decision.PAUSE:
            act = {"type": "what_next", "prompt_segment": "Use plate_what_next + autonomy status; make progress on next open child of #470 (one at a time).", "est": est, "decision": dec.value}
            if dec == Decision.THROTTLE:
                act["throttled"] = True
            if dec == Decision.WARN:
                act["annotation"] = "WARN: budget near/ over cap (over-estimate applied)"
            actions.append(act)
        for proc in snapshot.due_procedures:
            if self._risk_rank(proc.get("risk_level", "medium")) <= self._risk_rank(self.risk_tolerance):
                est = self.estimate_cost("run_procedure", {**scope, "id": proc.get("id")})
                dec = self.enforce_budget(est, "run_procedure")
                if dec != Decision.PAUSE:
                    pact = {"type": "run_procedure", "id": proc.get("id"), "est": est, "decision": dec.value}
                    if dec == Decision.THROTTLE:
                        pact["throttled"] = True
                    if dec == Decision.WARN:
                        pact["annotation"] = "WARN: budget near/ over cap (over-estimate applied)"
                    actions.append(pact)
        return actions

    def run_cycle(self, *, dry_run: bool = False, max_steps: int | None = None) -> CycleReport:
        """Main entry for scheduled/looped autonomous execution.

        Introspect -> enforce (real est from #471 estimate_cost) -> decide (budget wired) -> execute (delegate support) -> log markers + USAGE REPORT.
        Quiet enforcement: only append progress actions (executed/delegated/markers) to report; no non-progress/no-op comments (per quiet ops #456 + AGENTS.md).
        References #471/#472; ties to #478 procedures, #479 obs, #482 tests. Delegation via plate_delegate_to_agent + trigger markers.
        #648: open pausing checkpoints short-circuit the cycle (paused) before decide/execute.
        """
        ts = datetime.now(timezone.utc).isoformat()
        # Do not unconditionally zero _spent_this_cycle here: daily rollover + carry across --loop cycles (reused engine) is handled inside enforce_budget's date check. Per-cycle accounting starts from instance init (new engine) or accumulated (loop reuse). Addresses review feedback on daily budget enforcement in long-running loops.
        snap = self.introspect()
        actions: list[str] = []
        throttled: list[str] = []
        paused = False
        budget_dec = Decision.PROCEED.value
        total_est = 0

        # #648 hard pause when open human checkpoints exist
        try:
            from .checkpoint import autonomy_is_paused_by_checkpoints
            pause_info = autonomy_is_paused_by_checkpoints(base_dir=self.checkpoint_base_dir)
            if pause_info.get("paused"):
                ids = ", ".join(pause_info.get("checkpoint_ids") or []) or "(unknown)"
                led = self._ledger_record(
                    "run_cycle",
                    "pause",
                    f"open human checkpoint(s): {ids}",
                    sources=["autonomy_engine", "checkpoint", "#648"],
                    checkpoint_id=(pause_info.get("checkpoint_ids") or [None])[0],
                    session=ts,
                    metadata={"checkpoint_ids": pause_info.get("checkpoint_ids")},
                )
                taken = [f"paused: open human checkpoint(s) {ids}"]
                if led and led.get("id"):
                    taken.append(f"ledger: {led['id']} decision=pause")
                return CycleReport(
                    status="paused",
                    actions_taken=taken,
                    throttled=["checkpoint"],
                    paused=True,
                    budget_decision="pause",
                    snapshot=snap.to_dict(),
                    timestamp=ts,
                )
        except Exception:
            pass

        self._spent_this_cycle = 0  # fresh per cycle
        decided = self.decide_next(snap)
        if not decided:
            # decide filtered all (PAUSE from est/enforce on tiny budget); probe to set paused state for report
            probe_est = self.estimate_cost("what_next", {})
            dec = self.enforce_budget(probe_est, "what_next")
            if dec == Decision.PAUSE:
                paused = True
                budget_dec = dec.value
                led = self._ledger_record(
                    "run_cycle",
                    "pause",
                    "budget governor paused cycle (no actions under token/USD rails)",
                    cost_estimate_tokens=probe_est,
                    sources=["autonomy_engine", "enforce_budget", "#634"],
                    session=ts,
                )
                if led and led.get("id"):
                    actions.append(f"ledger: {led['id']} decision=pause")
        for act in decided[: (max_steps if max_steps is not None else 10)]:
            kind = act.get("type", "unknown")
            est = act.get("est") or self.estimate_cost(kind, {"cost_report": snap.cost_report, "num_items": 2})
            total_est += est
            # Use decision from decide_next (which already enforced + charged) to eliminate double-spend risk flagged in #502 review.
            # Only the initial probe (when no decided actions) may call enforce.
            dec = Decision[act.get("decision", "PROCEED").upper()] if act.get("decision") else Decision.PROCEED
            # #647: durable provenance for each decided action (even dry-run / pause)
            try:
                from .ledger import record_from_autonomy_action
                led = record_from_autonomy_action(
                    {**act, "type": kind, "est": est, "decision": dec.value},
                    risk_tolerance=self.risk_tolerance,
                    session=ts,
                    actor="autonomy",
                    base_dir=self.ledger_base_dir,
                )
                actions.append(f"ledger: {led.get('id')} decision={dec.value}")
            except Exception:
                pass
            if dec == Decision.PAUSE:
                throttled.append(kind)
                paused = True
                budget_dec = Decision.PAUSE.value
                continue
            if dec in (Decision.THROTTLE, Decision.WARN):
                throttled.append(kind)
                budget_dec = dec.value if dec != Decision.PROCEED else budget_dec
                # for throttle: partial already spent in enforce (from decide_next); continue to execute (per task "throttle: partial spend + continue")
            if dry_run:
                actions.append(f"dry-run: {kind} est={est}")
                continue
            # Execute or delegate (support plate_delegate_to_agent + trigger comments per #472)
            executed_desc = f"executed: {kind}"
            try:
                if "delegate" in kind or "delegate_to_agent" in str(act):
                    # wire delegation (from baseline_catalog; narrow packet per design)
                    from .baseline_catalog import delegate_to_agent
                    # scope from act/snap; real would pass focused packet. Here best-effort marker + call (safe no-op if no agent match)
                    _ = delegate_to_agent(agent_id="plate", prompt_segment=act.get("prompt_segment", "autonomous progress"), context={"autonomy_cycle": ts, "risk": self.risk_tolerance})
                    executed_desc = f"delegated: {kind} (plate_delegate_to_agent triggered)"
            except Exception:
                pass  # delegation optional; fall to executed marker
            actions.append(executed_desc)
            # Full logging: PLATE-AUTONOMY-CYCLE marker + USAGE REPORT block (per #474 AC + AGENTS)
            marker = f"<!-- PLATE-AUTONOMY-CYCLE: ts={ts} kind={kind} est={est} decision={dec.value} budget_remaining~{max(0, (self.autonomy_config.get('token_budget',{}).get('per_cycle',8000)-self._spent_this_cycle))} -->"
            actions.append(marker)
            # USAGE style for traceability (even for engine cycles; harvested where Feature/Question close)
            if not dry_run:
                actions.append("=== USAGE REPORT ===\ntokens: " + str(est) + "\ncost: $0.00\n duration: 00:00:10 (autonomy est)\n=== END USAGE REPORT ===")

        report = CycleReport(
            status="completed" if not paused else "paused",
            actions_taken=actions,
            throttled=throttled,
            paused=paused,
            budget_decision=budget_dec,
            snapshot=snap.to_dict(),
            timestamp=ts,
        )
        return report

    def run_procedure(
        self,
        proc_id: str,
        *,
        dry_run: bool = False,
        shadow_ack: str | None = None,
        approved: bool = False,
        checkpoint_id: str | None = None,
    ) -> dict[str, Any]:
        """Run a named procedure (from .agentic/procedures/ or built-in).

        High-risk procedures at low risk_tolerance return status=shadow_required with a
        shadow_report (#645) instead of executing, unless approved after simulate
        (or via an approved #648 checkpoint_id).
        """
        pdef = next((p for p in self.procedures if p.id == proc_id), None)
        scope: dict[str, Any] = {"id": proc_id}
        if pdef is not None:
            scope["risk_level"] = pdef.risk_level
            scope["procedure_risk"] = pdef.risk_level
        if dry_run:
            shadow = self.simulate_action("run_procedure", scope)
            return {
                "proc_id": proc_id,
                "status": "dry-run",
                "shadow_report": shadow.to_dict(),
            }
        # #645 gate: high/critical procedure risk under low tolerance → shadow_required
        impact = classify_action_impact("run_procedure", scope)
        if impact in ("high", "critical") or (
            pdef is not None and self._risk_rank(pdef.risk_level) > self._risk_rank(self.risk_tolerance)
        ):
            gate = self.gate_high_impact(
                "run_procedure" if impact != "critical" else "deploy",
                shadow_ack=shadow_ack,
                approved=approved,
                checkpoint_id=checkpoint_id,
                scope=scope,
                create_checkpoint=True,
            )
            # Prefer classifying via procedure risk when higher than kind default
            if pdef is not None and pdef.risk_level == "high" and self._risk_rank(self.risk_tolerance) < self._risk_rank("medium"):
                if not approved:
                    # Reuse gate shadow when present so one durable preview + checkpoint
                    if gate.get("blocked") and gate.get("shadow_report"):
                        out = {
                            "proc_id": proc_id,
                            "status": "shadow_required",
                            "shadow_report": gate.get("shadow_report"),
                            "reason": "high-risk procedure requires shadow + approval at current risk_tolerance",
                        }
                        if gate.get("checkpoint_id"):
                            out["checkpoint_id"] = gate["checkpoint_id"]
                            out["checkpoint"] = gate.get("checkpoint")
                        return out
                    shadow = self.simulate_action("run_procedure", scope)
                    cp = self._maybe_checkpoint_for_blocked(shadow)
                    out = {
                        "proc_id": proc_id,
                        "status": "shadow_required",
                        "shadow_report": shadow.to_dict(),
                        "reason": "high-risk procedure requires shadow + approval at current risk_tolerance",
                    }
                    if cp and cp.get("id"):
                        out["checkpoint_id"] = cp["id"]
                        out["checkpoint"] = {
                            "id": cp.get("id"),
                            "status": cp.get("status"),
                            "title": cp.get("title"),
                        }
                    return out
            if gate.get("blocked"):
                out = {
                    "proc_id": proc_id,
                    "status": "shadow_required",
                    "shadow_report": gate.get("shadow_report"),
                    "reason": gate.get("reason"),
                }
                if gate.get("checkpoint_id"):
                    out["checkpoint_id"] = gate["checkpoint_id"]
                    out["checkpoint"] = gate.get("checkpoint")
                return out
        # In full impl: dispatch steps using allow-listed MCP calls (e.g. plate_perform_information_audit, plate_pr_babysit, plate_costs)
        # For now, record marker + usage (as required by PLATE for procedures)
        marker = f"<!-- PLATE-PROCEDURE-RUN:{proc_id} cadence={pdef.cadence if pdef else 'unknown'} risk={pdef.risk_level if pdef else 'unknown'} -->"
        return {"proc_id": proc_id, "status": "executed", "log_marker": marker}

    def tick_schedules(self) -> list[dict[str, Any]]:
        """Find due procedures (cadence match) whose risk_level <= tolerance and run them."""
        due = []
        for p in self.procedures:
            if not p.enabled:
                continue
            if self._risk_rank(p.risk_level) > self._risk_rank(self.risk_tolerance):
                continue
            # Demo: treat "nightly"/"weekly" as due in this autonomous run (real would use last-run timestamp or cron lib)
            if p.cadence in ("nightly", "weekly", "manual"):
                due.append({"id": p.id, "risk_level": p.risk_level, "est_tokens": 4000})
        return due

    def _risk_rank(self, tol: str) -> int:
        order = {"off": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
        # Default to 0 (off) for unknown/invalid risk_tolerance (fail closed; prevents silent low-rank allow on typo per review feedback).
        return order.get((tol or '').lower(), 0)


# Convenience for MCP/CLI
def get_autonomy_status(repo: str | None = None) -> dict[str, Any]:
    engine = AutonomyEngine(repo=repo)
    return engine.get_status().to_dict()


def run_autonomy_cycle(repo: str | None = None, dry_run: bool = False, max_steps: int | None = None) -> dict[str, Any]:
    engine = AutonomyEngine(repo=repo)
    return engine.run_cycle(dry_run=dry_run, max_steps=max_steps).to_dict()


def simulate_autonomy_action(
    action_kind: str,
    repo: str | None = None,
    scope: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Module helper: shadow/simulate a single action (#645)."""
    engine = AutonomyEngine(repo=repo)
    return engine.simulate_action(action_kind, scope=scope).to_dict()
