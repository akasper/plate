"""Cost / usage aggregation surfaces for observability (Epic #265).

Harvests === USAGE REPORT === blocks from closed issues (per AGENTS.md convention
and plates-on-issue-closed workflow), parses tokens/cost/duration, aggregates,
and emits reports. Supports Epic filtering, JSON/MD output for wiki/release notes.

Integrates with accountant baseline agent (calculate-costs skill).
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

from .github_client import GhClient
from .health import resolve_repo


@dataclass
class UsageReport:
    date: str
    issue_number: int
    issue_title: str
    issue_type: str  # Feature, Question, etc.
    tokens: int
    cost: str  # e.g. "$0.12"
    duration: str  # e.g. "00:05:23"
    source_url: str  # comment url

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CostReport:
    repo: str
    total_tokens: int
    total_cost: str  # summed or note assumptions
    reports: list[UsageReport]
    assumptions: str = "Pricing from GitHub Copilot / Actions billing at time of report; durations proxy for compute. See .agentic/COSTS.md for raw."

    def to_dict(self) -> dict[str, Any]:
        return {
            "repo": self.repo,
            "total_tokens": self.total_tokens,
            "total_cost": self.total_cost,
            "assumptions": self.assumptions,
            "reports": [r.to_dict() for r in self.reports],
        }


USAGE_BLOCK_RE = re.compile(
    r"===\s*USAGE REPORT\s*===\s*\n?(.*?)(?:\n?===\s*END USAGE REPORT\s*===|$)",
    re.IGNORECASE | re.DOTALL,
)
TOKENS_RE = re.compile(r"tokens\s*:\s*(\d+)", re.IGNORECASE)
COST_RE = re.compile(r"cost\s*:\s*([^\n\r]+)", re.IGNORECASE)
DURATION_RE = re.compile(r"duration\s*:\s*([^\n\r]+)", re.IGNORECASE)


def _parse_usage_block(block: str) -> dict[str, Any] | None:
    tokens_m = TOKENS_RE.search(block)
    cost_m = COST_RE.search(block)
    dur_m = DURATION_RE.search(block)
    if not tokens_m:
        return None
    return {
        "tokens": int(tokens_m.group(1)),
        "cost": cost_m.group(1).strip() if cost_m else "n/a",
        "duration": dur_m.group(1).strip() if dur_m else "n/a",
    }


def harvest_usage_reports(
    repo: str | None = None,
    client: GhClient | None = None,
    issue_type_filter: str | None = None,
    epic_label: str | None = None,
    limit: int = 100,
) -> list[UsageReport]:
    """Harvest USAGE REPORT blocks from closed issues via GitHub search + comments.

    Prefers live GitHub data (workflow may lag). Respects privacy (no prompt content).
    """
    gh = client or GhClient()
    target = resolve_repo(repo)

    query = f"repo:{target} is:issue is:closed \"=== USAGE REPORT ===\""
    if issue_type_filter:
        query += f" label:{issue_type_filter}"
    if epic_label:
        query += f" label:\"{epic_label}\""

    search = gh.api(f"search/issues?q={query}&sort=updated&order=desc&per_page={min(limit,100)}")
    items = search.get("items", [])[:limit]

    reports: list[UsageReport] = []
    for issue in items:
        num = issue["number"]
        title = issue.get("title", "")
        labels = [l["name"] for l in issue.get("labels", [])]
        itype = next((l for l in labels if l in ("Feature", "Question", "Epic", "Bug", "Research", "Design", "Documentation")), "unknown")

        # Get comments for the report block (most recent first for the closing one)
        comments = gh.api(f"repos/{target}/issues/{num}/comments?per_page=50&sort=created&direction=desc") or []
        for c in comments:
            body = c.get("body") or ""
            m = USAGE_BLOCK_RE.search(body)
            if m:
                parsed = _parse_usage_block(m.group(1))
                if parsed:
                    reports.append(
                        UsageReport(
                            date=issue.get("closed_at") or issue.get("updated_at", ""),
                            issue_number=num,
                            issue_title=title,
                            issue_type=itype,
                            tokens=parsed["tokens"],
                            cost=parsed["cost"],
                            duration=parsed["duration"],
                            source_url=c.get("html_url", ""),
                        )
                    )
                break  # one per issue

    return reports


def get_cost_report(
    repo: str | None = None,
    client: GhClient | None = None,
    epic_label: str | None = None,
) -> CostReport:
    """Aggregate harvested reports into summary (for CLI/MCP)."""
    reports = harvest_usage_reports(repo=repo, client=client, epic_label=epic_label)
    total_tokens = sum(r.tokens for r in reports)
    # Simple sum note; real would parse $ amounts, but keep as string + assumption
    total_cost = f"${sum(float(r.cost.replace('$','').replace(',','') or 0) for r in reports):.2f}" if reports else "$0.00"
    target = resolve_repo(repo)
    return CostReport(repo=target, total_tokens=total_tokens, total_cost=total_cost, reports=reports)


def format_cost_markdown(report: CostReport) -> str:
    """Emit wiki-friendly MD table (for release notes / .agentic/COSTS.md style)."""
    lines = [
        f"# Cost Report for {report.repo}",
        "",
        report.assumptions,
        "",
        "| Date | Issue | Type | Tokens | Cost | Duration | Source |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in report.reports:
        issue_cell = f"[#{r.issue_number}](https://github.com/{report.repo}/issues/{r.issue_number}) {r.issue_title}"
        lines.append(f"| {r.date} | {issue_cell} | {r.issue_type} | {r.tokens} | {r.cost} | {r.duration} | [comment]({r.source_url}) |")
    lines.append("")
    lines.append(f"**Totals:** {report.total_tokens} tokens, {report.total_cost}")
    return "\n".join(lines)


def _parse_usd(cost_str: str | None) -> float:
    if not cost_str:
        return 0.0
    try:
        return float(str(cost_str).replace("$", "").replace(",", "").strip() or 0)
    except (TypeError, ValueError):
        return 0.0


def get_cost_dashboard(
    repo: str | None = None,
    client: GhClient | None = None,
    epic_label: str | None = None,
    *,
    autonomy_status: dict[str, Any] | None = None,
    health: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Cost + risk observability dashboard for the endless what-next feed (#653 / #634).

    Combines USAGE harvest totals with AutonomyEngine budget/risk signals:
    - burn_rate, remaining tokens/USD, enforcement action
    - autopilot_score + projected days of runway at current burn
    - open human checkpoints and due procedures (feed seeds)
    - drift/risk signals from health recommendations when provided
    - ranked feed_items for #631 consumers

    Network-light: pass autonomy_status/health to avoid extra GH calls in tests.
    """
    report = get_cost_report(repo=repo, client=client, epic_label=epic_label)
    cost_dict = report.to_dict()

    if autonomy_status is None:
        try:
            from .autonomy import get_autonomy_status
            autonomy_status = get_autonomy_status(repo)
        except Exception:
            autonomy_status = {}

    if health is None:
        health = {}
        # Only hit health when repo is set; avoid offline hangs
        if repo:
            try:
                from .health import get_health
                health = get_health(repo).to_dict()
            except Exception:
                health = {}

    daily = 50000
    per_cycle = 8000
    action_policy = "throttle"
    cost_ceiling = None
    try:
        from .plate_config import load_plate_config
        cfg = load_plate_config()
        auto = (cfg.to_dict() if hasattr(cfg, "to_dict") else {}).get("autonomy") or {}
        tb = auto.get("token_budget") or {}
        daily = int(tb.get("daily") or daily)
        per_cycle = int(tb.get("per_cycle") or per_cycle)
        action_policy = str(tb.get("action") or action_policy)
        if auto.get("cost_ceiling_usd") is not None:
            cost_ceiling = float(auto.get("cost_ceiling_usd"))
    except Exception:
        pass

    burn = float((autonomy_status or {}).get("burn_rate") or 0.0)
    remaining_tokens = (autonomy_status or {}).get("budget_remaining_tokens")
    if remaining_tokens is None:
        remaining_tokens = daily
    remaining_usd = (autonomy_status or {}).get("budget_remaining_usd")
    if remaining_usd is None:
        remaining_usd = cost_ceiling
    autopilot = int((autonomy_status or {}).get("autopilot_score") or 0)
    risk = str((autonomy_status or {}).get("risk_tolerance") or "off")
    enabled = bool((autonomy_status or {}).get("enabled", False))
    open_cps = list((autonomy_status or {}).get("open_human_checkpoints") or [])
    due_procs = list((autonomy_status or {}).get("due_procedures") or [])

    # Projected runway: if burn is % of daily budget, estimate days until empty
    projected_days_remaining: float | None
    if burn > 0:
        projected_days_remaining = round(max(0.0, (100.0 - burn) / burn), 2)
    elif remaining_tokens and daily:
        projected_days_remaining = None  # idle burn; unknown
    else:
        projected_days_remaining = None

    spent_tokens_est = max(0, daily - int(remaining_tokens or 0)) if daily else 0
    harvested_tokens = int(cost_dict.get("total_tokens") or 0)
    harvested_usd = _parse_usd(cost_dict.get("total_cost"))

    # Budget enforcement posture (#634 visibility)
    budget = {
        "daily_tokens": daily,
        "per_cycle_tokens": per_cycle,
        "action_on_breach": action_policy,  # throttle | pause | warn
        "cost_ceiling_usd": cost_ceiling,
        "remaining_tokens": remaining_tokens,
        "remaining_usd": remaining_usd,
        "burn_rate_pct": burn,
        "spent_tokens_est_today": spent_tokens_est,
        "spent_usd_est_today": round((spent_tokens_est / 1000.0) * 0.002, 6) if spent_tokens_est else 0.0,
        "enforcement_active": enabled and risk != "off",
        "would_throttle_at": max(0, daily - per_cycle) if action_policy == "throttle" else None,
        "durable_spend_note": "AutonomyEngine persists counters under .agentic/budget/spend.json (#634)",
    }

    # Drift / risk signals
    drift_signals: list[dict[str, Any]] = []
    for rec in (health.get("recommendations") or [])[:10]:
        drift_signals.append({"kind": "health_recommendation", "detail": str(rec), "impact": "medium"})
    for err in (health.get("errors") or [])[:10]:
        drift_signals.append({"kind": "health_error", "detail": str(err), "impact": "high"})
    if risk == "off" or not enabled:
        drift_signals.append({
            "kind": "autonomy_off",
            "detail": "Autonomy disabled or risk_tolerance=off — budgets not enforcing unsupervised runs",
            "impact": "low",
        })
    if cost_ceiling is not None and harvested_usd > cost_ceiling:
        drift_signals.append({
            "kind": "cost_ceiling_exceeded",
            "detail": f"Harvested cost {harvested_usd} exceeds ceiling {cost_ceiling}",
            "impact": "high",
        })
    if burn >= 80:
        drift_signals.append({
            "kind": "burn_high",
            "detail": f"Burn rate {burn}% of daily token budget",
            "impact": "high",
        })

    # Ranked feed items for what-next / #631
    feed_items: list[dict[str, Any]] = []
    for i, cp in enumerate(open_cps[:10]):
        feed_items.append({
            "rank": 10 + i,
            "type": "checkpoint",
            "title": str(cp),
            "impact": "high",
            "reason": "Open human checkpoint blocks unsupervised autonomy",
        })
    for i, proc in enumerate(due_procs[:10]):
        feed_items.append({
            "rank": 40 + i,
            "type": "procedure",
            "title": f"Due procedure: {proc}",
            "impact": "medium",
            "reason": "Scheduled procedure within risk_tolerance",
        })
    for i, sig in enumerate(drift_signals[:10]):
        feed_items.append({
            "rank": 20 + i if sig.get("impact") == "high" else 50 + i,
            "type": "drift",
            "title": sig.get("detail"),
            "impact": sig.get("impact", "medium"),
            "reason": f"Signal: {sig.get('kind')}",
        })
    # Cost hotspots from harvested reports (top issues by tokens)
    top_reports = sorted(report.reports, key=lambda r: r.tokens, reverse=True)[:5]
    for i, r in enumerate(top_reports):
        feed_items.append({
            "rank": 60 + i,
            "type": "cost_hotspot",
            "title": f"#{r.issue_number} {r.issue_title} ({r.tokens} tokens)",
            "impact": "medium" if r.tokens < 10000 else "high",
            "reason": "High USAGE REPORT spend",
            "issue_number": r.issue_number,
        })
    feed_items.sort(key=lambda x: (x.get("rank", 99), str(x.get("title") or "")))

    return {
        "repo": cost_dict.get("repo"),
        "generated_for": "cost_risk_dashboard",
        "issue_refs": ["#653", "#634", "#654"],
        "cost": {
            "total_tokens_harvested": harvested_tokens,
            "total_cost_harvested": cost_dict.get("total_cost"),
            "total_cost_usd": harvested_usd,
            "report_count": len(report.reports),
            "assumptions": cost_dict.get("assumptions"),
            "top_issues": [
                {
                    "issue_number": r.issue_number,
                    "title": r.issue_title,
                    "tokens": r.tokens,
                    "cost": r.cost,
                    "type": r.issue_type,
                }
                for r in top_reports
            ],
        },
        "budget": budget,
        "risk": {
            "risk_tolerance": risk,
            "autonomy_enabled": enabled,
            "autopilot_score": autopilot,
            "throttled_actions": (autonomy_status or {}).get("throttled_actions", 0),
        },
        "projections": {
            "burn_rate_pct": burn,
            "projected_days_remaining_at_burn": projected_days_remaining,
            "note": "Projection is heuristic from autonomy burn_rate % of daily budget; not a billing guarantee.",
        },
        "open_human_checkpoints": open_cps,
        "due_procedures": due_procs,
        "drift_signals": drift_signals,
        "feed_items": feed_items,
        "markdown": format_dashboard_markdown(
            repo=str(cost_dict.get("repo") or repo or ""),
            budget=budget,
            risk={"risk_tolerance": risk, "autonomy_enabled": enabled, "autopilot_score": autopilot},
            projections={"burn_rate_pct": burn, "projected_days_remaining_at_burn": projected_days_remaining},
            feed_items=feed_items[:15],
            harvested_tokens=harvested_tokens,
            harvested_cost=str(cost_dict.get("total_cost") or "$0.00"),
        ),
    }


def format_dashboard_markdown(
    *,
    repo: str,
    budget: dict[str, Any],
    risk: dict[str, Any],
    projections: dict[str, Any],
    feed_items: list[dict[str, Any]],
    harvested_tokens: int,
    harvested_cost: str,
) -> str:
    """Compact MD for wiki/CLI (#653)."""
    lines = [
        f"# Cost + Risk Dashboard — {repo}",
        "",
        f"- Autonomy: enabled={risk.get('autonomy_enabled')} risk_tolerance={risk.get('risk_tolerance')} autopilot={risk.get('autopilot_score')}",
        f"- Budget: daily={budget.get('daily_tokens')} remaining={budget.get('remaining_tokens')} burn={budget.get('burn_rate_pct')}% action={budget.get('action_on_breach')}",
        f"- Ceiling USD: {budget.get('cost_ceiling_usd')} | Harvested: {harvested_tokens} tokens / {harvested_cost}",
        f"- Projection days remaining (heuristic): {projections.get('projected_days_remaining_at_burn')}",
        "",
        "## Feed items (ranked)",
        "",
    ]
    if not feed_items:
        lines.append("_No feed items._")
    else:
        for item in feed_items:
            lines.append(
                f"- [{item.get('impact')}] {item.get('type')}: {item.get('title')} — {item.get('reason')}"
            )
    lines.append("")
    return "\n".join(lines)
