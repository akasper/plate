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
_FENCE_OPENER_RE = re.compile(r"^( {0,3})(`{3,}|~{3,})(.*)$")


def parse_fence_opener(line: str) -> tuple[str, int] | None:
    """Return (fence_char, fence_len) when ``line`` opens a fenced code block.

    Follows CommonMark: backtick openers are rejected when the info string
    (remainder after the opening run) contains a backtick. Tilde openers allow
    backticks in the info string.
    """
    bare = line.rstrip("\n\r")
    m = _FENCE_OPENER_RE.match(bare)
    if not m:
        return None
    run = m.group(2)
    info = m.group(3) or ""
    fence_char = run[0]
    if fence_char == "`" and "`" in info:
        return None
    return fence_char, len(run)


def _fence_closer_line(line: str, fence_char: str, min_len: int) -> bool:
    stripped = line.rstrip("\n\r")
    if fence_char == "`":
        pat = rf"^( {{0,3}})`{{{min_len},}}[ \t]*$"
    else:
        pat = rf"^( {{0,3}})~{{{min_len},}}[ \t]*$"
    return bool(re.match(pat, stripped))


def strip_closing_scan_text(markdown: str | None) -> str:
    """Remove HTML comments and fenced code blocks before scanning for closing keywords.

    Fence handling follows CommonMark: matching opener/closer delimiter character and
    run length (so four-backtick fences may contain triple-backtick lines). Content
    inside fences is dropped verbatim (including ``<!--`` markers). Unclosed fences
    drop the remainder of the document.
    """
    text = markdown or ""
    if not text:
        return ""

    lines = text.splitlines(keepends=True)
    out: list[str] = []
    in_fence = False
    fence_char = ""
    fence_len = 0
    i = 0
    while i < len(lines):
        line = lines[i]
        bare = line.rstrip("\n\r")
        if in_fence:
            if _fence_closer_line(bare, fence_char, fence_len):
                in_fence = False
                fence_char = ""
                fence_len = 0
            i += 1
            continue
        opener = parse_fence_opener(bare)
        if opener:
            fence_char, fence_len = opener
            in_fence = True
            i += 1
            continue
        out.append(line)
        i += 1

    joined = "".join(out)
    return _HTML_COMMENT_RE.sub("", joined)


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


def body_has_strict_closing_keyword(
    body: str | None,
    *,
    owner: str | None = None,
    repo: str | None = None,
) -> bool:
    """True when stripped body contains an explicit Closes/Fixes/Resolves reference."""
    cleaned = strip_closing_scan_text(body)
    owner_l = (owner or "").lower()
    repo_l = (repo or "").lower()
    for match in CLOSING_KEYWORD_STRICT_RE.finditer(cleaned):
        url_owner = match.group("url_owner")
        url_repo = match.group("url_repo")
        if url_owner and url_repo and owner and repo:
            if url_owner.lower() != owner_l or url_repo.lower() != repo_l:
                continue
        return True
    return False
