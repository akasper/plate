"""GitHub Discussions MCP surface and helpers (Feature #329).

Provides plate_* MCP tools and high-level functions for reading/updating
GitHub Discussions (e.g. Ideas category for process ideas, inter-agent comms/logs
as motivated by Ideas #287, #292, #293 and the What Next? MCP / orchestrator vision in Epic #282).

Uses GhClient (gh api + GraphQL) for resilience, secret redaction, etc.
Category filtering for "ideas" etc. is supported; create uses GraphQL (REST create not directly available).
"""

from __future__ import annotations

from dataclasses import dataclass, asdict

from .github_client import GhClient, GhApiError
from .health import resolve_repo


@dataclass
class Discussion:
    """Normalized discussion record for MCP / agent consumption."""

    number: int
    title: str
    html_url: str
    state: str
    created_at: str
    updated_at: str
    author: str | None = None
    body: str | None = None
    category: dict | None = None
    comments_count: int = 0

    def to_dict(self) -> dict:
        d = asdict(self)
        return {k: v for k, v in d.items() if v is not None}


@dataclass
class DiscussionComment:
    """Normalized comment record."""

    id: int
    body: str
    created_at: str
    author: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _get_gh() -> GhClient:
    return GhClient()


def list_discussions(
    repo: str | None = None,
    category: str | None = None,
    state: str | None = None,
    per_page: int = 30,
    page: int = 1,
) -> list[Discussion]:
    """List discussions (optionally filtered by category slug/name or state).

    Filtering for category/state is done post-fetch for reliability across GitHub API param quirks.
    """
    target = resolve_repo(repo)
    owner, name = target.split("/", 1)
    gh = _get_gh()
    qs = f"?per_page={per_page}&page={page}"
    # Note: use query string in endpoint (not -f fields) because /discussions list rejects form-encoded query params with 404 (observed); ? form works reliably.
    raw = gh.api(f"repos/{owner}/{name}/discussions{qs}") or []
    results: list[Discussion] = []
    for d in raw or []:
        cat = d.get("category") or {}
        if category:
            if cat.get("slug") != category and cat.get("name") != category:
                continue
        if state and (d.get("state") or "").lower() != state.lower():
            continue
        results.append(
            Discussion(
                number=d.get("number"),
                title=d.get("title", ""),
                html_url=d.get("html_url", ""),
                state=d.get("state", ""),
                created_at=d.get("created_at", ""),
                updated_at=d.get("updated_at", ""),
                author=(d.get("user") or {}).get("login"),
                body=d.get("body"),
                category=cat,
                comments_count=d.get("comments", 0),
            )
        )
    return results


def get_discussion(repo: str | None = None, number: int | None = None) -> Discussion:
    if number is None:
        raise ValueError("number is required")
    target = resolve_repo(repo)
    owner, name = target.split("/", 1)
    gh = _get_gh()
    d = gh.get_discussion(owner, name, int(number))
    cat = d.get("category") or {}
    return Discussion(
        number=d.get("number"),
        title=d.get("title", ""),
        html_url=d.get("html_url", ""),
        state=d.get("state", ""),
        created_at=d.get("created_at", ""),
        updated_at=d.get("updated_at", ""),
        author=(d.get("user") or {}).get("login"),
        body=d.get("body"),
        category=cat,
        comments_count=d.get("comments", 0),
    )


def list_discussion_comments(
    repo: str | None = None, number: int | None = None, per_page: int = 30
) -> list[DiscussionComment]:
    if number is None:
        raise ValueError("number is required")
    target = resolve_repo(repo)
    owner, name = target.split("/", 1)
    gh = _get_gh()
    qs = f"?per_page={per_page}"
    raw = gh.api(f"repos/{owner}/{name}/discussions/{int(number)}/comments{qs}") or []
    return [
        DiscussionComment(
            id=c.get("id"),
            body=c.get("body", ""),
            created_at=c.get("created_at", ""),
            author=(c.get("user") or {}).get("login"),
        )
        for c in (raw or [])
    ]


def add_discussion_comment(
    repo: str | None = None, number: int | None = None, body: str | None = None
) -> dict:
    if number is None or not body:
        raise ValueError("number and body are required")
    target = resolve_repo(repo)
    owner, name = target.split("/", 1)
    gh = _get_gh()
    return gh.add_discussion_comment(owner, name, int(number), body) or {}


def list_discussion_categories(repo: str | None = None) -> list[dict]:
    target = resolve_repo(repo)
    owner, name = target.split("/", 1)
    gh = _get_gh()
    return gh.list_discussion_categories(owner, name)


def create_discussion(
    repo: str | None = None,
    category_slug: str | None = None,
    category_id: str | None = None,
    title: str | None = None,
    body: str | None = None,
) -> dict:
    if not title or not body:
        raise ValueError("title and body are required")
    target = resolve_repo(repo)
    owner, name = target.split("/", 1)
    gh = _get_gh()
    if category_id is None:
        if not category_slug:
            raise ValueError("category_slug or category_id is required")
        cats = gh.list_discussion_categories(owner, name)
        match = next(
            (c for c in cats if c.get("slug") == category_slug or c.get("name") == category_slug), None
        )
        if not match:
            raise ValueError(f"Category '{category_slug}' not found")
        category_id = match["id"]
    return gh.create_discussion(owner, name, category_id, title, body)


def list_open_ideas(repo: str | None = None) -> list[Discussion]:
    """Convenience for the common 'Ideas' category use case (see Ideas #287 etc.)."""
    return list_discussions(repo=repo, category="ideas", state="open")
