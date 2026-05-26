"""Epic status queries shared across CLI and MCP surfaces."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from urllib.parse import quote_plus

from .github_client import GhClient
from .health import resolve_repo


@dataclass
class EpicSummary:
    epic_label: str
    epic_issue_number: int | None
    epic_issue_title: str | None
    epic_issue_state: str | None
    open_child_issues: int
    closed_child_issues: int

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class EpicStatusReport:
    repo: str
    open_epic_count: int
    epics: list[EpicSummary]

    def to_dict(self) -> dict:
        return {
            "repo": self.repo,
            "open_epic_count": self.open_epic_count,
            "epics": [x.to_dict() for x in self.epics],
        }


def _search_issues(client: GhClient, query: str) -> dict:
    return client.api(f"search/issues?q={quote_plus(query)}")


def get_epic_status(repo: str | None = None, client: GhClient | None = None) -> EpicStatusReport:
    gh = client or GhClient()
    target = resolve_repo(repo)

    labels = gh.api(f"repos/{target}/labels?per_page=100")
    epic_labels = sorted([x["name"] for x in labels if x["name"].startswith("Epic: ")])

    open_epics = int(_search_issues(gh, f"repo:{target} is:issue is:open label:Epic").get("total_count", 0))
    summaries: list[EpicSummary] = []

    for label in epic_labels:
        epic_issue_resp = _search_issues(
            gh, f'repo:{target} is:issue label:Epic label:"{label}" sort:updated-desc'
        )
        epic_issue = (epic_issue_resp.get("items") or [None])[0]
        open_children = int(
            _search_issues(gh, f'repo:{target} is:issue is:open -label:Epic label:"{label}"').get("total_count", 0)
        )
        closed_children = int(
            _search_issues(gh, f'repo:{target} is:issue is:closed -label:Epic label:"{label}"').get("total_count", 0)
        )
        summaries.append(
            EpicSummary(
                epic_label=label,
                epic_issue_number=(epic_issue or {}).get("number"),
                epic_issue_title=(epic_issue or {}).get("title"),
                epic_issue_state=(epic_issue or {}).get("state"),
                open_child_issues=open_children,
                closed_child_issues=closed_children,
            )
        )

    return EpicStatusReport(repo=target, open_epic_count=open_epics, epics=summaries)

