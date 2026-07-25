"""Human + agent safe co-existence helpers (#643 / #651).

First slice (#643):
- driver:* labels (human | agent | collaborative) on issues/PRs
- pause delegation when driver:human
- PR authorship mix (human vs bot commits) for transparency
- collab policy check before high-stakes agent git ops
- PLATE-COLLAB markers for auditable feed/logs

Etiquette slice (#651):
- Durable path/branch ownership claims under .agentic/collab/ownership.json
- Pause-autonomy-on-path gestures agents must respect
- Worktree isolation + concurrent-edit etiquette checks
- Feed presentation for open human ownership claims

Does not replace CODEOWNERS or branch protection — complements them.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MARKER_BEGIN = "<!-- PLATE-COLLAB:BEGIN -->"
MARKER_END = "<!-- PLATE-COLLAB:END -->"

DRIVER_HUMAN = "driver:human"
DRIVER_AGENT = "driver:agent"
DRIVER_COLLAB = "driver:collaborative"
DRIVER_LABELS = (DRIVER_HUMAN, DRIVER_AGENT, DRIVER_COLLAB)

OWNERSHIP_DIR = Path(".agentic/collab")
OWNERSHIP_FILE = "ownership.json"

# Heuristic bot / agent logins (extend via config later)
_BOT_LOGIN_RE = re.compile(
    r"(?i)(\[bot\]$|bot$|copilot|dependabot|renovate|github-actions|"
    r"devin-ai|openhands|plate-agent|codecov)"
)

# Protected integration branch names agents must not treat as personal worktrees
_INTEGRATION_BRANCHES = frozenset(
    {"main", "master", "release", "release-major", "release-minor", "release-patch"}
)
_INTEGRATION_PREFIXES = ("release-v", "release/")


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
    paths: list[str] | None = None,
    branch: str | None = None,
    worktree_root: str | None = None,
    repo_root: str | None = None,
    base_dir: Path | None = None,
) -> dict[str, Any]:
    """Gate common agent actions against human co-existence rules.

    Returns {allowed, reason, escalate, driver, action, ...extra #651 fields}.
    """
    action_n = (action or "").lower().replace("-", "_")
    driver = get_driver(labels)
    auth = authorship
    if isinstance(authorship, AuthorshipReport):
        auth = authorship.to_dict()
    auth = auth or {}
    mix = str(auth.get("mix") or "")
    extra: dict[str, Any] = {}

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

    # #651: durable path/branch ownership pauses
    if paths:
        blocked = paths_blocked_for_agent(paths, base_dir=base_dir)
        if blocked and action_n in (
            "delegate",
            "push_branch",
            "open_pr",
            "apply_suggestion",
            "edit_files",
            "auto_merge",
            "write",
            "commit",
        ):
            ids = [c.get("id") for c in blocked]
            return {
                "allowed": False,
                "reason": (
                    f"path ownership pause active ({len(blocked)} claim(s)); "
                    f"release with plate_collab_ownership_release or wait for human"
                ),
                "escalate": True,
                "driver": driver,
                "action": action_n,
                "blocked_claims": blocked,
                "claim_ids": ids,
            }
        if blocked:
            extra["blocked_claims"] = blocked

    if branch:
        bc = branch_claim_for(branch, base_dir=base_dir)
        if bc and str(bc.get("owner") or "").lower() == "human" and action_n in (
            "push_branch",
            "force_push",
            "git_push_force",
            "reset_hard_remote",
            "open_pr",
            "auto_merge",
            "delegate",
        ):
            return {
                "allowed": False,
                "reason": f"branch '{branch}' claimed by human (claim {bc.get('id')})",
                "escalate": True,
                "driver": driver,
                "action": action_n,
                "blocked_claims": [bc],
                "claim_ids": [bc.get("id")],
            }
        if action_n in ("push_branch", "commit", "open_pr", "edit_files"):
            etiq = branch_etiquette_check(branch, worktree_root=worktree_root, repo_root=repo_root)
            extra["branch_etiquette"] = etiq
            if not etiq.get("ok") and action_n in ("push_branch", "commit", "edit_files"):
                return {
                    "allowed": False,
                    "reason": etiq.get("reason") or "branch etiquette failed",
                    "escalate": True,
                    "driver": driver,
                    "action": action_n,
                    **extra,
                }

    return {
        "allowed": True,
        "reason": "ok",
        "escalate": False,
        "driver": driver,
        "action": action_n,
        **extra,
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


# --- #651 path/branch ownership + worktree etiquette ---


def _normalize_path(p: str) -> str:
    s = str(p or "").strip().replace("\\", "/")
    while s.startswith("./"):
        s = s[2:]
    return s.rstrip("/")


def _path_matches(claim_path: str, candidate: str) -> bool:
    """True if candidate is claim_path or a descendant (prefix match on dirs)."""
    c = _normalize_path(claim_path)
    t = _normalize_path(candidate)
    if not c or not t:
        return False
    if c == t:
        return True
    # Directory claim covers children
    if t.startswith(c.rstrip("/") + "/"):
        return True
    return False


def _ownership_path(base_dir: Path | None = None) -> Path:
    d = base_dir or OWNERSHIP_DIR
    return d / OWNERSHIP_FILE if d.name != "ownership.json" else d


def _load_ownership(base_dir: Path | None = None) -> dict[str, Any]:
    path = _ownership_path(base_dir)
    if not path.exists():
        return {"version": 1, "claims": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"version": 1, "claims": []}
        data.setdefault("version", 1)
        data.setdefault("claims", [])
        if not isinstance(data["claims"], list):
            data["claims"] = []
        return data
    except (OSError, json.JSONDecodeError):
        return {"version": 1, "claims": []}


def _save_ownership(data: dict[str, Any], base_dir: Path | None = None) -> Path:
    path = _ownership_path(base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return path


def claim_ownership(
    *,
    kind: str,
    target: str,
    owner: str = "human",
    reason: str = "",
    related_issue: int | None = None,
    actor: str = "human",
    base_dir: Path | None = None,
) -> dict[str, Any]:
    """Record a path or branch ownership claim (pause autonomy gesture).

    kind: path | branch
    owner: human | agent | collaborative
    """
    kind_n = (kind or "path").lower().strip()
    if kind_n not in ("path", "branch"):
        kind_n = "path"
    target_n = _normalize_path(target) if kind_n == "path" else str(target or "").strip()
    if not target_n:
        return {"ok": False, "error": "target required"}
    owner_n = (owner or "human").lower().strip()
    if owner_n not in ("human", "agent", "collaborative"):
        owner_n = "human"
    data = _load_ownership(base_dir)
    # Dedupe: refresh existing open claim for same kind+target
    for c in data["claims"]:
        if c.get("status") != "open" or c.get("kind") != kind_n:
            continue
        existing = str(c.get("target") or "")
        same = (
            _normalize_path(existing) == target_n
            if kind_n == "path"
            else existing == target_n
        )
        if same:
            c["owner"] = owner_n
            c["reason"] = reason or c.get("reason") or ""
            c["related_issue"] = related_issue if related_issue is not None else c.get("related_issue")
            c["updated_at"] = _now()
            c["actor"] = actor
            _save_ownership(data, base_dir)
            return {"ok": True, "claim": c, "updated": True, "marker": render_collab_marker(c)}

    claim = {
        "id": f"own-{uuid.uuid4().hex[:10]}",
        "kind": kind_n,
        "target": target_n,
        "owner": owner_n,
        "reason": reason or f"{owner_n} claims {kind_n} {target_n}",
        "related_issue": related_issue,
        "status": "open",
        "actor": actor,
        "created_at": _now(),
        "updated_at": _now(),
    }
    data["claims"].append(claim)
    _save_ownership(data, base_dir)
    return {"ok": True, "claim": claim, "updated": False, "marker": render_collab_marker(claim)}


def release_ownership(
    claim_id: str | None = None,
    *,
    kind: str | None = None,
    target: str | None = None,
    base_dir: Path | None = None,
) -> dict[str, Any]:
    """Close ownership claim(s) by id or kind+target."""
    data = _load_ownership(base_dir)
    released: list[dict[str, Any]] = []
    for c in data["claims"]:
        if c.get("status") != "open":
            continue
        match = False
        if claim_id and c.get("id") == claim_id:
            match = True
        elif kind and target:
            kn = kind.lower().strip()
            tn = _normalize_path(target) if kn == "path" else str(target).strip()
            if c.get("kind") == kn and (
                (_normalize_path(str(c.get("target") or "")) == tn)
                if kn == "path"
                else str(c.get("target") or "") == tn
            ):
                match = True
        if match:
            c["status"] = "released"
            c["released_at"] = _now()
            c["updated_at"] = _now()
            released.append(c)
    if not released:
        return {"ok": False, "error": "no open claim matched", "released": []}
    _save_ownership(data, base_dir)
    return {"ok": True, "released": released, "n": len(released)}


def list_ownership_claims(
    *,
    status: str = "open",
    kind: str | None = None,
    limit: int = 50,
    base_dir: Path | None = None,
) -> list[dict[str, Any]]:
    data = _load_ownership(base_dir)
    out: list[dict[str, Any]] = []
    for c in data.get("claims") or []:
        if status and status != "all" and c.get("status") != status:
            continue
        if kind and c.get("kind") != kind:
            continue
        out.append(c)
    return out[: max(1, int(limit or 50))]


def paths_blocked_for_agent(
    paths: list[str],
    *,
    base_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """Return open human/collaborative path claims that cover any of paths."""
    claims = list_ownership_claims(status="open", kind="path", limit=200, base_dir=base_dir)
    blocked: list[dict[str, Any]] = []
    seen: set[str] = set()
    for p in paths or []:
        for c in claims:
            if str(c.get("owner") or "").lower() not in ("human", "collaborative"):
                continue
            if _path_matches(str(c.get("target") or ""), p):
                cid = str(c.get("id") or "")
                if cid not in seen:
                    seen.add(cid)
                    blocked.append(c)
    return blocked


def branch_claim_for(branch: str, *, base_dir: Path | None = None) -> dict[str, Any] | None:
    b = str(branch or "").strip()
    if not b:
        return None
    for c in list_ownership_claims(status="open", kind="branch", limit=200, base_dir=base_dir):
        if str(c.get("target") or "") == b:
            return c
    return None


def is_integration_branch(branch: str | None) -> bool:
    b = str(branch or "").strip()
    if not b:
        return False
    if b in _INTEGRATION_BRANCHES:
        return True
    return any(b.startswith(p) for p in _INTEGRATION_PREFIXES)


def branch_etiquette_check(
    branch: str | None,
    *,
    worktree_root: str | None = None,
    repo_root: str | None = None,
) -> dict[str, Any]:
    """Agent branch/worktree etiquette (#651).

    Agents should use feature/* or bug/* (or epic/*) branches in isolated worktrees,
    not push directly on main/release or the primary checkout when a worktree is expected.
    """
    b = str(branch or "").strip()
    notes: list[str] = []
    ok = True
    reason = "ok"

    if not b:
        return {"ok": False, "reason": "branch required for etiquette check", "notes": notes}

    if is_integration_branch(b):
        ok = False
        reason = f"do not agent-edit integration branch '{b}' directly; use feature/* or bug/*"
        notes.append(reason)
    elif not re.match(r"^(feature|bug|docs|chore|hotfix|epic)/", b):
        notes.append(
            f"branch '{b}' lacks conventional type/ prefix; prefer feature/* or bug/* for agent work"
        )
        # Soft warn only — not a hard block for oddly named PR branches

    if worktree_root and repo_root:
        wr = str(Path(worktree_root).resolve())
        rr = str(Path(repo_root).resolve())
        if wr == rr:
            ok = False
            reason = "worktree not isolated — primary checkout equals worktree root (#514/#651)"
            notes.append(reason)

    return {
        "ok": ok,
        "reason": reason,
        "branch": b,
        "integration": is_integration_branch(b),
        "notes": notes,
    }


def concurrent_edit_risk(
    paths: list[str],
    *,
    base_dir: Path | None = None,
) -> dict[str, Any]:
    """Predict concurrent-edit risk from open ownership claims covering paths."""
    blocked = paths_blocked_for_agent(paths, base_dir=base_dir)
    # Also flag agent-owned claims as coordination risk (not hard block)
    agent_claims: list[dict[str, Any]] = []
    for p in paths or []:
        for c in list_ownership_claims(status="open", kind="path", limit=200, base_dir=base_dir):
            if str(c.get("owner") or "").lower() != "agent":
                continue
            if _path_matches(str(c.get("target") or ""), p):
                if c not in agent_claims and c not in blocked:
                    agent_claims.append(c)
    level = "none"
    if blocked:
        level = "blocked"
    elif agent_claims:
        level = "coordinate"
    return {
        "level": level,
        "human_claims": blocked,
        "agent_claims": agent_claims,
        "paths": list(paths or []),
        "advice": (
            "Pause — human owns overlapping paths"
            if level == "blocked"
            else (
                "Coordinate with other agent claim before overlapping edits"
                if level == "coordinate"
                else "No open ownership conflicts"
            )
        ),
    }


def ownership_feed_items(
    *,
    limit: int = 10,
    base_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """Present open human/collaborative ownership pauses for the endless feed."""
    items: list[dict[str, Any]] = []
    for c in list_ownership_claims(status="open", limit=limit * 2, base_dir=base_dir):
        owner = str(c.get("owner") or "")
        if owner not in ("human", "collaborative"):
            continue
        kind = c.get("kind")
        target = c.get("target")
        cid = c.get("id")
        title = f"Ownership pause: {kind} {target}"
        items.append(
            {
                "id": cid,
                "item_type": "collab_ownership",
                "title": title,
                "kind": kind,
                "target": target,
                "owner": owner,
                "reason": c.get("reason") or title,
                "badges": ["collab", "ownership", owner],
                "source": "collab_ownership",
                "impact": "high" if owner == "human" else "medium",
                "ask_user_question": {
                    "question": f"Path/branch ownership active on {target}. What next?",
                    "options": [
                        {
                            "id": "keep",
                            "label": "Keep pause",
                            "description": "Agents continue to skip this path/branch",
                        },
                        {
                            "id": "release",
                            "label": "Release claim",
                            "description": f"plate_collab_ownership_release / gh plate collab --release {cid}",
                        },
                    ],
                },
                "marker": render_collab_marker(
                    {"id": cid, "kind": kind, "target": target, "owner": owner, "status": "open"}
                ),
            }
        )
        if len(items) >= limit:
            break
    return items
