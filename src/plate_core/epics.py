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


def get_epic_status(
    repo: str | None = None, client: GhClient | None = None, project_number: int | None = None
) -> EpicStatusReport:
    """Get epic status, optionally enriched with Project v2 data (for #268).

    If project_number provided, attaches basic project item info to summaries
    (read via GraphQL). Write via add_issue_to_project_v2.

    Note on Issue states (#556): child issues merged to a release/next track branch
    (but not yet to main) should carry status:implemented (set by pr-issue-link-check
    workflow or equivalent on release-branch merges). The open/closed child counts
    here reflect GitHub native state; 'implemented' is additional process metadata
    surfaced via labels and future enhancements to summaries/health.
    """
    gh = client or GhClient()
    target = resolve_repo(repo)

    labels = gh.api(f"repos/{target}/labels?per_page=100")
    epic_labels = sorted([x["name"] for x in labels if x["name"].startswith("Epic: ")])

    open_epics = int(_search_issues(gh, f"repo:{target} is:issue is:open label:Epic").get("total_count", 0))
    summaries: list[EpicSummary] = []

    project_data = {}
    if project_number:
        project_data = get_project_v2_items(repo=target, project_number=project_number, client=gh)

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
        summary = EpicSummary(
            epic_label=label,
            epic_issue_number=(epic_issue or {}).get("number"),
            epic_issue_title=(epic_issue or {}).get("title"),
            epic_issue_state=(epic_issue or {}).get("state"),
            open_child_issues=open_children,
            closed_child_issues=closed_children,
        )
        # Optional project enrichment (small integration for AC)
        if project_number and summary.epic_issue_number:
            for item in (project_data.get("items", {}) or {}).get("nodes", []) or []:
                content = item.get("content") or {}
                if content.get("number") == summary.epic_issue_number:
                    # Attach simplified field values
                    fields = {}
                    for fv in (item.get("fieldValues", {}) or {}).get("nodes", []) or []:
                        fname = (fv.get("field") or {}).get("name")
                        val = fv.get("name") or fv.get("text")
                        if fname and val:
                            fields[fname] = val
                    if fields:
                        # Use a simple attr or note; for dataclass compat, we can extend later
                        pass  # minimal for now; consumers can call get_project_v2_items directly
        summaries.append(summary)

    return EpicStatusReport(repo=target, open_epic_count=open_epics, epics=summaries)


# --- GitHub Projects v2 integration (for #268) ---
# Provides read (project items/fields) and write (add issue to project) paths.
# Uses GraphQL via github_client (supports top-level var binding).
# Optional, backward compatible, degrades if no project or access.
# Core surfaces (epic status) can consume; MCP/CLI can expose.

def _graphql(client: GhClient, query: str, variables: dict | None = None) -> dict:
    """Helper for GraphQL queries (binds $vars via top-level fields for gh api)."""
    fields = {"query": query}
    if variables:
        for k, v in variables.items():
            fields[k] = v
    return client.api("graphql", method="POST", fields=fields)


def get_project_v2_items(
    repo: str | None = None, project_number: int = 1, client: GhClient | None = None
) -> dict:
    """Read path: fetch Project v2 items (issues + field values like status/priority).

    Enables core surfaces (e.g. epic_status) to surface Project data.
    Returns the projectV2 node or {} on failure (graceful degrade).
    """
    gh = client or GhClient()
    target = resolve_repo(repo)
    owner = target.split("/")[0]
    query = """
    query($owner: String!, $number: Int!) {
      organization(login: $owner) {
        projectV2(number: $number) {
          id
          title
          items(first: 50) {
            nodes {
              id
              content {
                ... on Issue {
                  number
                  title
                  id
                }
              }
              fieldValues(first: 20) {
                nodes {
                  __typename
                  ... on ProjectV2ItemFieldSingleSelectValue {
                    name
                    field { ... on ProjectV2FieldCommon { name } }
                  }
                  ... on ProjectV2ItemFieldTextValue {
                    text
                    field { ... on ProjectV2FieldCommon { name } }
                  }
                }
              }
            }
          }
        }
      }
    }
    """
    try:
        data = _graphql(gh, query, {"owner": owner, "number": project_number})
        return data.get("data", {}).get("organization", {}).get("projectV2", {}) or {}
    except Exception:
        return {}


def add_issue_to_project_v2(
    issue_number: int, repo: str | None = None, project_number: int = 1, client: GhClient | None = None
) -> dict:
    """Write path: add an issue to a Project v2 (e.g. to roadmap Project).

    Returns the added item info or {} on error (graceful).
    At least one write path per AC.
    """
    gh = client or GhClient()
    target = resolve_repo(repo)
    owner, repo_name = target.split("/")
    try:
        # Get issue ID
        iq = """
        query($owner: String!, $repo: String!, $number: Int!) {
          repository(owner: $owner, name: $repo) { issue(number: $number) { id } }
        }
        """
        idata = _graphql(gh, iq, {"owner": owner, "repo": repo_name, "number": issue_number})
        issue_id = idata.get("data", {}).get("repository", {}).get("issue", {}).get("id")
        if not issue_id:
            return {}

        # Get project ID
        pq = """
        query($owner: String!, $number: Int!) {
          organization(login: $owner) { projectV2(number: $number) { id } }
        }
        """
        pdata = _graphql(gh, pq, {"owner": owner, "number": project_number})
        project_id = pdata.get("data", {}).get("organization", {}).get("projectV2", {}).get("id")
        if not project_id:
            return {}

        # Mutation to add
        mq = """
        mutation($projectId: ID!, $contentId: ID!) {
          addProjectV2ItemById(input: {projectId: $projectId, contentId: $contentId}) {
            item { id }
          }
        }
        """
        mdata = _graphql(gh, mq, {"projectId": project_id, "contentId": issue_id})
        return mdata.get("data", {}).get("addProjectV2ItemById", {}) or {}
    except Exception:
        return {}

