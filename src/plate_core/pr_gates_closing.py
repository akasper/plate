"""Closing-keyword and markdown helpers for PLATE PR gates (#1231)."""

from __future__ import annotations

import re

# Strict closing keywords: require `#N` or a full GitHub issue URL (not bare digits).
CLOSING_KEYWORD_STRICT_RE = re.compile(
    r"\b(closes?|closed|fixe?s?|fixed|resolve[sd]?)\s+"
    r"(?:https?://github\.com/(?P<url_owner>[^/\s]+)/(?P<url_repo>[^/\s]+)/issues/(?P<url_num>\d+)"
    r"|#(?P<hash_num>\d+))\b",
    re.IGNORECASE,
)

_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_FENCED_CODE_RE = re.compile(r"```[^\n]*\n.*?```", re.DOTALL)


def strip_closing_scan_text(markdown: str | None) -> str:
    """Remove HTML comments and fenced code blocks before scanning for closing keywords."""
    text = markdown or ""
    text = _HTML_COMMENT_RE.sub("", text)
    text = _FENCED_CODE_RE.sub("", text)
    return text


def parse_strict_closing_issue_numbers(
    body: str | None,
    *,
    owner: str | None = None,
    repo: str | None = None,
) -> list[int]:
    """Parse issue numbers from closing keywords in stripped PR body text."""
    cleaned = strip_closing_scan_text(body)
    seen: set[int] = set()
    out: list[int] = []
    owner_l = (owner or "").lower()
    repo_l = (repo or "").lower()
    for match in CLOSING_KEYWORD_STRICT_RE.finditer(cleaned):
        url_owner = match.group("url_owner")
        url_repo = match.group("url_repo")
        num_s = match.group("url_num") or match.group("hash_num")
        if not num_s:
            continue
        num = int(num_s)
        if url_owner and url_repo and owner and repo:
            if url_owner.lower() != owner_l or url_repo.lower() != repo_l:
                continue
        if num not in seen:
            seen.add(num)
            out.append(num)
    return out


def body_has_strict_closing_keyword(body: str | None) -> bool:
    """True when stripped body contains an explicit Closes/Fixes/Resolves reference."""
    cleaned = strip_closing_scan_text(body)
    return bool(CLOSING_KEYWORD_STRICT_RE.search(cleaned))
