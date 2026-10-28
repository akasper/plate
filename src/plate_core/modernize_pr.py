"""Helpers for the modernize-pr skill workflow (#1235).

Ideas adapted from t3dotgg/tstack ``modernize`` (MIT, Theo Browne); this module is PLATE-original.
"""

from __future__ import annotations

VERDICT_MODERNIZE = "MODERNIZE"
VERDICT_REWORK = "REWORK"
VERDICT_CLOSE = "CLOSE"

VALID_VERDICTS = frozenset({VERDICT_MODERNIZE, VERDICT_REWORK, VERDICT_CLOSE})


def parse_verdict_line(line: str) -> str | None:
    """Return a normalized verdict token from a line such as ``Verdict: MODERNIZE``."""
    stripped = line.strip()
    if not stripped:
        return None
    upper = stripped.upper()
    for token in VALID_VERDICTS:
        if upper == token or upper.endswith(f": {token}") or upper.endswith(f" {token}"):
            return token
    if upper.startswith("VERDICT:"):
        candidate = upper.split(":", 1)[1].strip().split()[0] if ":" in upper else ""
        if candidate in VALID_VERDICTS:
            return candidate
    return None


def git_range_diff_argv(*, base: str, pre_rebase_head: str, post_rebase_head: str) -> list[str]:
    """Build ``git range-diff`` argv comparing pre- and post-rebase commit ranges onto ``base``."""
    base = base.strip()
    pre = pre_rebase_head.strip()
    post = post_rebase_head.strip()
    if not base or not pre or not post:
        raise ValueError("base, pre_rebase_head, and post_rebase_head are required")
    return [
        "git",
        "range-diff",
        f"{base}...{pre}",
        f"{base}...{post}",
    ]


def git_push_force_with_lease_argv(
    *,
    remote: str,
    branch: str,
    pre_rebase_head: str,
) -> list[str]:
    """Build ``git push --force-with-lease`` argv pinned to the pre-rebase head SHA."""
    remote = remote.strip()
    branch = branch.strip()
    pre = pre_rebase_head.strip()
    if not remote or not branch or not pre:
        raise ValueError("remote, branch, and pre_rebase_head are required")
    ref = f"refs/heads/{branch}"
    return [
        "git",
        "push",
        remote,
        branch,
        f"--force-with-lease={ref}:{pre}",
    ]
