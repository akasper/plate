"""Human + agent safe co-existence helpers (#643).

First slice:
- driver:* labels (human | agent | collaborative) on issues/PRs
- pause delegation when driver:human
- PR authorship mix (human vs bot commits) for transparency
- collab policy check before high-stakes agent git ops
- PLATE-COLLAB markers for auditable feed/logs

Does not replace CODEOWNERS or branch protection — complements them.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

MARKER_BEGIN = "<!-- PLATE-COLLAB:BEGIN -->"
MARKER_END = "<!-- PLATE-COLLAB:END -->"

DRIVER_HUMAN = "driver:human"
DRIVER_AGENT = "driver:agent"
DRIVER_COLLAB = "driver:collaborative"
DRIVER_LABELS = (DRIVER_HUMAN, DRIVER_AGENT, DRIVER_COLLAB)

# Heuristic bot / agent logins (extend via config later)
_BOT_LOGIN_RE = re.compile(
    r"(?i)(\[bot\]$|bot$|copilot|dependabot|renovate|github-actions|"
    r"devin-ai|openhands|plate-agent|codecov)"
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _labels_of(obj: dict[str, Any] | None) -> list[str]:
    out: list[str] = []
    for lab in (obj or {}).get("labels") or []:
        if isinstance(lab, dict):
            n = lab.get("name")
            if n:
                out.append(str(n))
        else:
            out.append(str(lab))
    return out


def is_bot_login(login: str | None) -> bool:
    if not login:
        return False
    return bool(_BOT_LOGIN_RE.search(str(login).strip()))


def get_driver(labels: list[str] | None) -> str:
    """Return driver mode from labels; default agent (agents may work unless human claimed)."""
    labs = {str(x).lower() for x in (labels or [])}
    if DRIVER_HUMAN in labs:
        return "human"
    if DRIVER_COLLAB in labs:
        return "collaborative"
    if DRIVER_AGENT in labs:
        return "agent"
    return "agent"


def should_pause_delegation(labels: list[str] | None) -> bool:
    """True when PM/Autonomy should not auto-delegate (human driving)."""
    return get_driver(labels) == "human"


def should_prefer_human_review(labels: list[str] | None) -> bool:
    """True when agent should not self-merge and should escalate to human review."""
    labs = {str(x).lower() for x in (labels or [])}
    if get_driver(labels) in ("human", "collaborative"):
        return True
    if "need:human-review" in labs or "need:security-review" in labs:
        return True
    if "risk:high" in labs or "risk:critical" in labs:
        return True
    return False


@dataclass
class AuthorshipReport:
    pr_number: int | None
    author_login: str | None
    author_is_bot: bool
    human_commits: int = 0
    bot_commits: int = 0
    unknown_commits: int = 0
    mix: str = "unknown"  # human | agent | mixed | empty
    human_logins: list[str] = field(default_factory=list)
    bot_logins: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def analyze_pr_authorship(
    *,
    pr_number: int | None = None,
    author_login: str | None = None,
    commits: list[dict[str, Any]] | None = None,
) -> AuthorshipReport:
    """Classify PR authorship mix from commit list + PR author.

    commits entries: {author: {login}|login|commit.author.name}
    """
    author_bot = is_bot_login(author_login)
    humans: set[str] = set()
    bots: set[str] = set()
    h_n = b_n = u_n = 0
    for c in commits or []:
        login = None
        if isinstance(c.get("author"), dict):
            login = c["author"].get("login")
        elif isinstance(c.get("author"), str):
            login = c.get("author")
        if not login and isinstance(c.get("commit"), dict):
            a = (c["commit"].get("author") or {})
            login = a.get("username") or a.get("name")
        if not login:
            u_n += 1
            continue
        login_s = str(login)
        if is_bot_login(login_s):
            bots.add(login_s)
            b_n += 1
        else:
            humans.add(login_s)
            h_n += 1

    if h_n and b_n:
        mix = "mixed"
    elif h_n and not b_n:
        mix = "human"
    elif b_n and not h_n:
        mix = "agent"
    elif author_login:
        mix = "agent" if author_bot else "human"
    else:
        mix = "empty" if not (commits or []) else "unknown"

    notes: list[str] = []
    if mix == "mixed":
        notes.append("Mixed human+agent commits — do not force-push; coordinate before rewrite history.")
    if mix == "human" and not author_bot:
        notes.append("Human-led PR — agents should not push unless explicitly directed.")
    if should_prefer_human_review([DRIVER_COLLAB] if mix == "mixed" else []):
        pass

    return AuthorshipReport(
        pr_number=pr_number,
        author_login=author_login,
        author_is_bot=author_bot,
        human_commits=h_n,
        bot_commits=b_n,
        unknown_commits=u_n,
        mix=mix,
        human_logins=sorted(humans),
        bot_logins=sorted(bots),
        notes=notes,
    )


def collab_policy_check(
    action: str,
    *,
    labels: list[str] | None = None,
    authorship: AuthorshipReport | dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Gate common agent actions against human co-existence rules.

    Returns {allowed, reason, escalate, driver, action}.
    """
    action_n = (action or "").lower().replace("-", "_")
    driver = get_driver(labels)
    auth = authorship
    if isinstance(authorship, AuthorshipReport):
        auth = authorship.to_dict()
    auth = auth or {}
    mix = str(auth.get("mix") or "")

    # Always escalate: never force-push mixed or human PRs
    if action_n in ("force_push", "git_push_force", "reset_hard_remote"):
        if mix in ("human", "mixed") or driver == "human":
            return {
                "allowed": False,
                "reason": "force-push blocked on human/mixed authorship or driver:human",
                "escalate": True,
                "driver": driver,
                "action": action_n,
            }

    if driver == "human":
        if action_n in (
            "delegate",
            "auto_merge",
            "push_branch",
            "open_pr",
            "apply_suggestion",
            "resolve_threads",
        ):
            return {
                "allowed": False,
                "reason": "driver:human — pause agent auto-work; human owns this item",
                "escalate": True,
                "driver": driver,
                "action": action_n,
            }

    if action_n == "auto_merge" and (
        should_prefer_human_review(labels) or mix == "mixed"
    ):
        return {
            "allowed": False,
            "reason": "auto-merge blocked for collaborative/high-risk/mixed PR",
            "escalate": True,
            "driver": driver,
            "action": action_n,
        }

    if mix == "human" and action_n in ("push_branch", "apply_suggestion"):
        return {
            "allowed": False,
            "reason": "human-led PR — require explicit human direction before agent push",
            "escalate": True,
            "driver": driver,
            "action": action_n,
        }

    return {
        "allowed": True,
        "reason": "ok",
        "escalate": False,
        "driver": driver,
        "action": action_n,
    }


def render_collab_marker(payload: dict[str, Any]) -> str:
    data = dict(payload)
    data.setdefault("ts", _now())
    return f"{MARKER_BEGIN}\n{json.dumps(data, indent=2)}\n{MARKER_END}\n"


def collab_status_for_issue(issue: dict[str, Any]) -> dict[str, Any]:
    """Summarize collab state for one issue (labels-based)."""
    labels = _labels_of(issue)
    driver = get_driver(labels)
    return {
        "number": issue.get("number"),
        "title": issue.get("title"),
        "driver": driver,
        "pause_delegation": should_pause_delegation(labels),
        "prefer_human_review": should_prefer_human_review(labels),
        "labels": labels,
        "marker": render_collab_marker(
            {
                "number": issue.get("number"),
                "driver": driver,
                "pause_delegation": should_pause_delegation(labels),
            }
        ),
    }


def filter_work_for_driver(
    items: list[dict[str, Any]],
    *,
    skip_human_driver: bool = True,
) -> dict[str, Any]:
    """Split work items by driver for PM/autonomy assign loops."""
    assignable: list[dict[str, Any]] = []
    paused: list[dict[str, Any]] = []
    for it in items:
        labels = it.get("labels") or []
        if labels and isinstance(labels[0], dict):
            labels = _labels_of(it)
        if skip_human_driver and should_pause_delegation(labels):
            paused.append(it)
        else:
            assignable.append(it)
    return {
        "assignable": assignable,
        "paused_human_driver": paused,
        "n_assignable": len(assignable),
        "n_paused": len(paused),
    }
