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
