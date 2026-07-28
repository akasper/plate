"""Local PR feedback babysitting helpers.

The pr-babysit skill/MCP surface (`gh plate pr babysit` or `plate_pr_babysit`) is the dedicated tool for PR feedback and health work. Agents must default to it (rather than hand-rolling git/gh commands) for "babysit", "get CI passing", "address feedback", or "make PR green" instructions (addresses #524 and related). After addressing feedback, explicitly resolve the corresponding review threads (via resolveReviewThread) to satisfy the feedback-resolution check (addresses #520).

**Auto-resolve on act (addresses #605):** When `act=True`, `babysit_pr` automatically resolves unresolved review threads that are **outdated** (typically after code was pushed that addresses the comment lines). This closes the gap where threads stayed `isResolved: false` after fixes, blocking the feedback-resolution gate even though the tool reported 0 actionable (outdated) threads. Explicit `resolve_review_thread` remains available for non-outdated threads and manual cases.

**Per #513: agents MUST run `gh plate release status` *proactively as the very first step* before calling babysit_pr, creating related PRs, or any targeting/base decision. This function assumes the caller has done so to confirm the correct track/base and pending fragments; use the output to set context.**

Review thread handling (GraphQL pagination via reviewThreads first:100 + nodes, exact databaseId from comments, author filtering, isResolved/isOutdated, body, resolveReviewThread mutation) is fully encapsulated in the high-level helpers: babysit_pr (for detection + report), get_actionable_review_threads (for listing), resolve_review_thread (for safe resolution), and get_pr_merge_gates. Agents and calling code **must not** manually construct raw `gh api graphql`, jq filters, mktemp tempfiles, sed/NO_COLOR ANSI stripping, or the mutation. Use the Python/MCP/CLI surfaces instead (addresses #516).

Worktree isolation for local-rebase (and general PR fix/babysit flows) is now more robust: helpers for lock cleanup, verification (git rev-parse --show-toplevel), and the rebase uses isolated worktree with better cleanup on errors/locks. Agents must use/verify isolated worktrees for any local changes during babysit or fixes; never pollute main checkout. (Addresses #514.)

**Mandatory first step in any verification/babysit/repro flow (addresses #527):** "CI diagnosis first" — *always* fetch `gh pr checks <N>` + identify the exact failing job/run + `gh run view <run> --job <job> --log-failed` (or equivalent structured) *before* any broad/expensive local command (e.g. full pytest in worktree). Only after seeing the real current error (labels? threads? specific test failure?) decide minimal scope or if local repro is even needed. Use cheap GitHub inspection before investing CPU/time.

During babysit or green-loop work, own the *full* "current failing gates" model and "make mergeable" loop (per agent_guidance "Full PR Green / Make Mergeable Loop" + new "CI Diagnosis First Protocol" and AGENTS.md babysit section):
- Start (and re-start after pushes) by comprehensively inspecting *all* gates, *beginning with* the CI diagnosis one-liners above (threads via the tool, base sync, labels, etc.).
- Address everything agent-actionable in the worktree (rebase, apply safe suggestions, resolve addressed threads via plate_resolve_review_thread, fix local tests with targeted scope only, etc.).
- Push to the *existing* PR branch only.
- Re-inspect (starting again with CI diagnosis).
- Repeat until only human-judgment items remain (e.g. owner CHANGES_REQUESTED, credentials, high-risk decisions). Only then report the one-sentence summary of what is left for the human.
- Use quiet terse bullets for looped turns. Escalate with need:human-review for judgment items.

The skill supports (via --act, --branch-update-strategy, and the returned BabysitReport) the inspect-fix-push-reinspect cycle for a *single high-level "turn this PR green" prompt*. The agent should handle all agent-actionable gates (conflicts, labels, threads, tests) comprehensively without category-by-category user prompting. Prefer or expose "until-green" / comprehensive make-mergeable behavior. Follow long-running command protocol for any backgrounded verification during the loop (record task_id, poll, cheap fallback on kill; see #529). Always start verification with CI diagnosis first (see #527). (Addresses #519, #528, #526, etc.)

See quiet_operations guidance (including new CI Diagnosis First and Full PR Green sections), plate.agent.md, and AGENTS.md for the full procedure (addresses #528, #527, #526, #519, #510, etc.).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

from .github_client import GhClient
from .health import resolve_repo


# Known bot / automated reviewer logins and patterns (#496 expands beyond early third-party list).
_DEFAULT_AGENT_PATTERNS = [
    re.compile(r"^devin", re.IGNORECASE),
    re.compile(r"^openhands", re.IGNORECASE),
    re.compile(r"^codegen", re.IGNORECASE),
    re.compile(r"^swe-agent", re.IGNORECASE),
    re.compile(r"^aide-agent", re.IGNORECASE),
    re.compile(r"^mentat-bot", re.IGNORECASE),
    re.compile(r"copilot", re.IGNORECASE),  # copilot-pull-request-reviewer, github-copilot, etc.
    re.compile(r"^dependabot", re.IGNORECASE),
    re.compile(r"^github-actions", re.IGNORECASE),
    re.compile(r"^coderabbit", re.IGNORECASE),
    re.compile(r"^cursor", re.IGNORECASE),
    re.compile(r"\[bot\]$", re.IGNORECASE),
]

_BABYSIT_MARKER = "<!-- plate-pr-babysit -->"
_MERGE_TRIGGER_MARKER = "<!-- plate-pr-merge-trigger -->"

# Valid branch update strategies
_VALID_STRATEGIES = ["copilot-request", "local-rebase", "none"]
_DEFAULT_STRATEGY = "copilot-request"

# #496: who counts as actionable review feedback
PR_REVIEW_SCOPES = ("all", "bot-only", "human-only")
_DEFAULT_PR_REVIEW_SCOPE = "all"
_SUGGESTION_FENCE_RE = re.compile(r"```suggestion[^\n]*\n(.*?)```", re.IGNORECASE | re.DOTALL)
_HIGH_RISK_PATH_FRAGMENTS = (
    "agents.md",
    ".github/workflows/",
    "spec.md",
    "current.md",
    ".plate",
    "credentials",
    "secret",
    "id_rsa",
    ".env",
    "pyproject.toml",  # version/publish surface
)


@dataclass
class BabysitReport:
    repo: str
    pr_number: int
    detected_threads: int
    actionable_threads: int
    trigger_comment_posted: bool
    trigger_comment_url: str | None = None
    out_of_sync: bool = False
    merge_state: str | None = None
    merge_trigger_posted: bool = False
    merge_trigger_url: str | None = None
    local_rebase_performed: bool = False
    local_rebase_success: bool | None = None
    local_rebase_conflict: bool = False
    local_rebase_error: str | None = None
    # #605: threads auto-resolved because they were outdated + unresolved when act=True
    auto_resolved_threads: int = 0
    auto_resolved_thread_ids: list[str] | None = None
    auto_resolve_errors: list[str] | None = None
    # #496: scope + suggestion awareness
    pr_review_scope: str = _DEFAULT_PR_REVIEW_SCOPE
    threads_with_suggestions: int = 0
    high_risk_suggestion_threads: int = 0
    actionable_thread_summaries: list[dict] | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _default_agent_match(login: str) -> bool:
    """True if login looks like a known bot/agent reviewer (#496)."""
    return any(pattern.search(login or "") for pattern in _DEFAULT_AGENT_PATTERNS)


def _is_bot_login(login: str) -> bool:
    """Alias for bot/agent detection used by pr_review_scope filtering."""
    return _default_agent_match(login)


def extract_suggestion_blocks(body: str | None) -> list[str]:
    """Return fenced ```suggestion``` block bodies from a review comment (#496)."""
    if not body:
        return []
    return [m.group(1).strip("\n") for m in _SUGGESTION_FENCE_RE.finditer(body)]


def _path_is_high_risk(path: str | None) -> bool:
    if not path:
        return False
    lower = path.replace("\\", "/").lower()
    return any(frag in lower for frag in _HIGH_RISK_PATH_FRAGMENTS)


def resolve_pr_review_scope(
    scope: str | None = None,
    *,
    repo_root: str | Path | None = None,
) -> str:
    """Resolve pr_review_scope: explicit arg > .plate autonomy > default ``all`` (#496)."""
    if scope:
        normalized = scope.strip().lower().replace("_", "-")
        if normalized not in PR_REVIEW_SCOPES:
            raise ValueError(f"Invalid pr_review_scope: {scope!r}. Must be one of {PR_REVIEW_SCOPES}")
        return normalized
    try:
        from .plate_config import load_plate_config

        conf = load_plate_config(repo_root or ".")
        auto = getattr(conf, "autonomy", None) or {}
        if isinstance(auto, dict):
            cfg_scope = auto.get("pr_review_scope")
            if cfg_scope:
                return resolve_pr_review_scope(str(cfg_scope))
    except Exception:
        pass
    return _DEFAULT_PR_REVIEW_SCOPE


def _detect_base_branch_out_of_sync(pr_data: dict) -> dict:
    """Detect if PR branch is out of sync with base branch.

    Args:
        pr_data: PR data containing mergeStateStatus and branch refs

    Returns:
        dict with keys:
            - out_of_sync (bool): Whether PR is out of sync
            - state (str): The mergeStateStatus value
            - base_ref (str): Base branch name
            - head_ref (str): Head branch name
    """
    merge_state = pr_data.get("mergeStateStatus", "")
    out_of_sync_states = ["BEHIND", "CONFLICTING", "DIRTY"]

    return {
        "out_of_sync": merge_state in out_of_sync_states,
        "state": merge_state,
        "base_ref": pr_data.get("baseRefName", ""),
        "head_ref": pr_data.get("headRefName", ""),
    }


def _parse_agent_logins(agent_logins: str | None) -> set[str]:
    if not agent_logins:
        return set()
    return {item.strip().lower() for item in agent_logins.split(",") if item.strip()}


def _author_in_scope(
    author: str,
    *,
    scope: str,
    agent_logins: str | None,
) -> bool:
    """Decide if a review author is actionable under scope / explicit allowlist (#496).

    Explicit ``agent_logins`` (CLI ``--agents``) remains an allowlist that overrides scope.
    """
    configured = _parse_agent_logins(agent_logins)
    lower = (author or "").strip().lower()
    if configured:
        return lower in configured
    is_bot = _is_bot_login(author)
    if scope == "all":
        return True
    if scope == "bot-only":
        return is_bot
    if scope == "human-only":
        return not is_bot
    return True


def _extract_actionable_threads(
    threads: list[dict],
    agent_logins: str | None,
    *,
    scope: str | None = None,
) -> list[dict]:
    """Extract unresolved, non-outdated threads in scope (#496).

    Default scope is ``all`` (every author) so Copilot and human reviewers are not dropped.
    Use ``bot-only`` for the pre-#496 conservative behavior (expanded bot patterns still apply).
    """
    effective_scope = resolve_pr_review_scope(scope) if scope is not None else resolve_pr_review_scope(None)
    # When agent_logins is set, scope is overridden by allowlist; still record effective intent.
    actionable: list[dict] = []
    for thread in threads:
        if thread.get("isResolved") or thread.get("isOutdated"):
            continue
        comments = (thread.get("comments") or {}).get("nodes") or []
        if not comments:
            continue
        last = comments[-1]
        author = ((last.get("author") or {}).get("login") or "").strip()
        if not _author_in_scope(author, scope=effective_scope, agent_logins=agent_logins):
            continue
        body = (last.get("body") or "").strip()
        suggestions = extract_suggestion_blocks(body)
        path = thread.get("path") or last.get("path") or ""
        high_risk = _path_is_high_risk(path)
        actionable.append(
            {
                "thread_id": thread.get("id"),
                "comment_id": last.get("databaseId"),
                "author": author,
                "url": last.get("url"),
                "body": body,
                "is_bot": _is_bot_login(author),
                "has_suggestion": bool(suggestions),
                "suggestion_count": len(suggestions),
                "suggestions": suggestions,
                "path": path,
                "high_risk_path": high_risk,
                # Prefer apply only when suggestion present, path not high-risk, and bot/all scope trusts bots more
                "prefer_apply_suggestion": bool(suggestions) and not high_risk,
            }
        )
    return actionable


def _extract_outdated_unresolved_threads(threads: list[dict]) -> list[dict]:
    """Threads that are still open but outdated (code moved) — candidates for auto-resolve (#605).

    Outdated + unresolved is the common post-fix state: agent addressed the line(s) and pushed,
    so GitHub marks the thread outdated, but feedback-resolution CI still fails until
    resolveReviewThread is called.
    """
    candidates: list[dict] = []
    for thread in threads:
        if thread.get("isResolved"):
            continue
        if not thread.get("isOutdated"):
            continue
        thread_id = thread.get("id")
        if not thread_id:
            continue
        comments = (thread.get("comments") or {}).get("nodes") or []
        last = comments[-1] if comments else {}
        author = ((last.get("author") or {}).get("login") or "").strip()
        candidates.append(
            {
                "thread_id": thread_id,
                "comment_id": last.get("databaseId"),
                "author": author,
                "url": last.get("url"),
                "body": (last.get("body") or "").strip(),
            }
        )
    return candidates


def _load_review_threads(client: GhClient, repo: str, pr_number: int) -> list[dict]:
    """Load review threads only. For backward compatibility."""
    pr_data = _load_pr_data(client, repo, pr_number)
    return pr_data.get("reviewThreads", [])


def _summarize_status_check_rollup(rollup: dict | None) -> dict:
    """Normalize GitHub statusCheckRollup into failing/pending counts + state.

    Used by get_pr_merge_gates and evaluate_babysit_gates for #638/#639 loop advance.
    """
    if not isinstance(rollup, dict):
        return {
            "ci_state": None,
            "failing_checks": 0,
            "pending_checks": 0,
            "ci_failing": False,
            "ci_pending": False,
        }
    state = str(rollup.get("state") or "").upper() or None
    failing = 0
    pending = 0
    contexts = rollup.get("contexts") or rollup.get("nodes") or []
    if isinstance(contexts, dict):
        contexts = contexts.get("nodes") or []
    for ctx in contexts or []:
        if not isinstance(ctx, dict):
            continue
        # CheckRun: status (QUEUED/IN_PROGRESS/COMPLETED) + conclusion
        conclusion = str(ctx.get("conclusion") or "").upper()
        status = str(ctx.get("status") or ctx.get("state") or "").upper()
        if conclusion in ("FAILURE", "TIMED_OUT", "CANCELLED", "ACTION_REQUIRED", "STARTUP_FAILURE"):
            failing += 1
        elif status in ("FAILURE", "ERROR"):
            failing += 1
        elif status in ("PENDING", "EXPECTED", "QUEUED", "IN_PROGRESS", "REQUESTED", "WAITING"):
            pending += 1
        elif conclusion in ("", "NEUTRAL", "SKIPPED") and status in ("", "COMPLETED"):
            continue
    # Prefer rollup aggregate when contexts missing
    if failing == 0 and pending == 0 and state:
        if state in ("FAILURE", "ERROR"):
            failing = 1
        elif state in ("PENDING", "EXPECTED"):
            pending = 1
    return {
        "ci_state": state,
        "failing_checks": failing,
        "pending_checks": pending,
        "ci_failing": failing > 0 or state in ("FAILURE", "ERROR"),
        "ci_pending": pending > 0 or state in ("PENDING", "EXPECTED"),
    }


def evaluate_babysit_gates(
    gates: dict | None,
    *,
    require_ci_success: bool = True,
    block_on_pending_ci: bool = True,
) -> dict:
    """Decide whether bug/feature loops may leave babysit (or merge_eligible).

    Pure helper for #638/#639 advance gates. When ``gates`` is None, not blocked
    (caller did not supply inspection). When present, blocks on:
    - merge_state in BLOCKED/DIRTY/CONFLICTING/BEHIND
    - unresolved / actionable agent review threads
    - review_decision == CHANGES_REQUESTED
    - CI failing (and optionally pending) when require_ci_success
    - explicit need_human_review / labels containing need:human-review (soft: reason only
      when also force-blocking via gates['block_human_review']=True — default False so
      requires_human routing handles it)

    Returns:
        {blocked: bool, reason: str|None, checks: dict snapshot}
    """
    if not gates:
        return {"blocked": False, "reason": None, "checks": {}}

    merge_state = str(
        gates.get("merge_state") or gates.get("mergeStateStatus") or ""
    ).upper()
    unresolved = int(
        gates.get("unresolved_review_threads")
        or gates.get("actionable_agent_threads")
        or 0
    )
    # Prefer explicit actionable agent count for thread gate when both present
    if gates.get("actionable_agent_threads") is not None and gates.get(
        "unresolved_review_threads"
    ) is not None:
        unresolved = max(
            int(gates.get("unresolved_review_threads") or 0),
            int(gates.get("actionable_agent_threads") or 0),
        )
    review_decision = str(
        gates.get("review_decision") or gates.get("reviewDecision") or ""
    ).upper()
    ci_failing = bool(gates.get("ci_failing"))
    ci_pending = bool(gates.get("ci_pending"))
    failing_checks = int(gates.get("failing_checks") or 0)
    pending_checks = int(gates.get("pending_checks") or 0)
    if failing_checks > 0:
        ci_failing = True
    if pending_checks > 0:
        ci_pending = True
    ci_state = str(gates.get("ci_state") or "").upper()
    if ci_state in ("FAILURE", "ERROR"):
        ci_failing = True
    if ci_state in ("PENDING", "EXPECTED"):
        ci_pending = True

    checks = {
        "merge_state": merge_state or None,
        "unresolved_review_threads": unresolved,
        "review_decision": review_decision or None,
        "ci_failing": ci_failing,
        "ci_pending": ci_pending,
        "failing_checks": failing_checks,
        "pending_checks": pending_checks,
        "ci_state": ci_state or None,
    }

    if merge_state in ("BLOCKED", "DIRTY", "CONFLICTING", "BEHIND"):
        return {
            "blocked": True,
            "reason": f"PR not clean ({merge_state}); stay on babysit",
            "checks": checks,
        }
    if unresolved > 0:
        return {
            "blocked": True,
            "reason": f"{unresolved} unresolved threads; stay on babysit",
            "checks": checks,
        }
    if review_decision == "CHANGES_REQUESTED":
        return {
            "blocked": True,
            "reason": "review_decision=CHANGES_REQUESTED; stay on babysit",
            "checks": checks,
        }
    if require_ci_success and ci_failing:
        n = failing_checks or 1
        return {
            "blocked": True,
            "reason": f"CI failing ({n} check(s)); stay on babysit",
            "checks": checks,
        }
    if require_ci_success and block_on_pending_ci and ci_pending:
        n = pending_checks or 1
        return {
            "blocked": True,
            "reason": f"CI pending ({n} check(s)); stay on babysit",
            "checks": checks,
        }
    if gates.get("block_human_review"):
        labels = gates.get("labels") or []
        if gates.get("need_human_review") or any(
            str(x) == "need:human-review" for x in labels
        ):
            return {
                "blocked": True,
                "reason": "need:human-review; stay on babysit/human_checkpoint",
                "checks": checks,
            }

    return {"blocked": False, "reason": None, "checks": checks}


def _load_pr_data(client: GhClient, repo: str, pr_number: int) -> dict:
    """Load PR data including review threads, merge state, review decision, CI rollup.

    Returns:
        dict with keys:
            - reviewThreads (list): List of review thread nodes
            - mergeStateStatus (str): Merge state (CLEAN, BEHIND, CONFLICTING, DIRTY, etc)
            - baseRefName (str): Base branch name
            - headRefName (str): Head branch name
            - reviewDecision (str|None): APPROVED / CHANGES_REQUESTED / REVIEW_REQUIRED / None
            - statusCheckRollup (dict|None): GitHub rollup for head commit checks
    """
    owner, name = repo.split("/", 1)
    query = """
query($owner: String!, $repo: String!, $number: Int!) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $number) {
      mergeStateStatus
      baseRefName
      headRefName
      reviewDecision
      statusCheckRollup {
        state
      }
      reviewThreads(first: 100) {
        nodes {
          id
          isResolved
          isOutdated
          path
          comments(last: 5) {
            nodes {
              databaseId
              body
              url
              path
              author {
                login
              }
            }
          }
        }
      }
    }
  }
}
""".strip()
    payload = client.api(
        "graphql",
        method="POST",
        fields={
            "query": query,
            "owner": owner,
            "repo": name,
            "number": pr_number,
        },
    )
    pr = (
        ((payload or {}).get("data") or {})
        .get("repository", {})
        .get("pullRequest", {})
    )
    return {
        "reviewThreads": (pr.get("reviewThreads", {}) or {}).get("nodes", []),
        "mergeStateStatus": pr.get("mergeStateStatus", "UNKNOWN"),
        "baseRefName": pr.get("baseRefName", ""),
        "headRefName": pr.get("headRefName", ""),
        "reviewDecision": pr.get("reviewDecision"),
        "statusCheckRollup": pr.get("statusCheckRollup"),
    }


def _has_existing_babysit_comment(client: GhClient, repo: str, pr_number: int) -> bool:
    comments = client.api(f"repos/{repo}/issues/{pr_number}/comments?per_page=100&sort=created&direction=desc")
    return any(_BABYSIT_MARKER in ((c or {}).get("body") or "") for c in comments or [])


def _has_existing_merge_trigger_comment(client: GhClient, repo: str, pr_number: int) -> bool:
    """Check if merge trigger comment already exists to avoid duplicates."""
    comments = client.api(f"repos/{repo}/issues/{pr_number}/comments?per_page=100&sort=created&direction=desc")
    return any(_MERGE_TRIGGER_MARKER in ((c or {}).get("body") or "") for c in comments or [])


def _post_babysit_trigger(
    client: GhClient,
    repo: str,
    pr_number: int,
    actionable_threads: list[dict],
    *,
    scope: str = _DEFAULT_PR_REVIEW_SCOPE,
) -> str | None:
    thread_lines = []
    for item in actionable_threads:
        flags = []
        if item.get("has_suggestion"):
            flags.append("suggestion")
        if item.get("prefer_apply_suggestion"):
            flags.append("prefer-apply")
        if item.get("high_risk_path"):
            flags.append("high-risk-path")
        flag_s = f" [{', '.join(flags)}]" if flags else ""
        thread_lines.append(
            f"- {item.get('url')} (thread `{item.get('thread_id')}` by @{item.get('author')}){flag_s}"
        )
    body = "\n".join(
        [
            _BABYSIT_MARKER,
            "@copilot Start PR feedback babysitting for this pull request.",
            "",
            f"Scope: `{scope}` (autonomy.pr_review_scope / --scope). Address *all* listed threads.",
            "Actionable review threads:",
            *thread_lines,
            "",
            "Workflow requirements:",
            "1. Prefer applying ```suggestion``` blocks when present and path is not high-risk; else code change or terse rationale.",
            "2. Push changes to this same PR branch (do not open a new PR).",
            "3. Resolve each addressed thread (`plate_resolve_review_thread` / resolveReviewThread). Outdated threads auto-resolve on babysit --act (#605).",
            "4. High-risk paths (AGENTS.md, workflows, SPEC, secrets, .plate, …): do not auto-apply; add `need:human-review` if blocked.",
            "5. Do not re-request Copilot review in a loop; work the existing threads first (#496).",
        ]
    )
    response = client.api(
        f"repos/{repo}/issues/{pr_number}/comments",
        method="POST",
        fields={"body": body},
    )
    return (response or {}).get("html_url")


def _post_merge_trigger(client: GhClient, repo: str, pr_number: int, sync_info: dict) -> str | None:
    """Post a Copilot merge-request trigger comment.

    Args:
        client: GitHub client
        repo: Repository identifier (owner/name)
        pr_number: Pull request number
        sync_info: Dict with base_ref, head_ref, and state

    Returns:
        URL of posted comment or None
    """
    base_ref = sync_info.get("base_ref", "base")
    head_ref = sync_info.get("head_ref", "head")
    state = sync_info.get("state", "out-of-sync")

    body = "\n".join(
        [
            _MERGE_TRIGGER_MARKER,
            f"@copilot This PR branch (`{head_ref}`) is out of sync with the base branch (`{base_ref}`).",
            f"Merge state: `{state}`",
            "",
            "Please update this branch to resolve the merge conflict or bring it up to date with the base branch.",
        ]
    )
    response = client.api(
        f"repos/{repo}/issues/{pr_number}/comments",
        method="POST",
        fields={"body": body},
    )
    return (response or {}).get("html_url")


def _perform_local_rebase(base_ref: str, head_ref: str, repo_dir: str | None = None) -> dict:
    """Perform a local rebase of head_ref onto base_ref using an isolated git worktree.

    Returns a dict with:
        success: bool
        conflict: bool
        error: str | None
        output: str | None
    Safe: does not modify current working tree; cleans up worktree on exit.
    """
    if not base_ref or not head_ref:
        return {"success": False, "conflict": False, "error": "missing base or head ref", "output": None}

    if repo_dir is None:
        # detect from cwd
        try:
            repo_dir = subprocess.check_output(
                ["git", "rev-parse", "--show-toplevel"], text=True, cwd="."
            ).strip()
        except Exception as e:
            return {"success": False, "conflict": False, "error": f"not in git repo: {e}", "output": None}

    worktree_path = None
    try:
        # Robust lock cleanup before any git ops (addresses #514 lock incidents from prior failed babysits/subagents)
        cleanup_git_locks(repo_dir)
        # Verify we are (or will operate) in appropriate tree context
        v = verify_worktree_is_isolated()
        if not v["is_isolated"]:
            # still proceed for rebase (which creates its own worktree) but surface warning
            pass
        # fresh fetch
        subprocess.check_call(["git", "-C", repo_dir, "fetch", "origin", base_ref, head_ref], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        worktree_path = tempfile.mkdtemp(prefix="plate-babysit-rebase-")
        # add worktree at the head_ref tip
        subprocess.check_call(
            ["git", "-C", repo_dir, "worktree", "add", "--detach", worktree_path, f"origin/{head_ref}"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )

        # rebase in the worktree
        rebase_res = subprocess.run(
            ["git", "-C", worktree_path, "rebase", f"origin/{base_ref}"],
            capture_output=True, text=True
        )
        if rebase_res.returncode != 0:
            # abort to clean
            subprocess.run(["git", "-C", worktree_path, "rebase", "--abort"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return {
                "success": False,
                "conflict": True,
                "error": "rebase conflict or failure",
                "output": (rebase_res.stdout or "") + (rebase_res.stderr or ""),
            }

        # push back (force-with-lease for safety)
        push_res = subprocess.run(
            ["git", "-C", worktree_path, "push", "origin", f"HEAD:{head_ref}", "--force-with-lease"],
            capture_output=True, text=True
        )
        if push_res.returncode != 0:
            return {
                "success": False,
                "conflict": False,
                "error": "push after rebase failed",
                "output": (push_res.stdout or "") + (push_res.stderr or ""),
            }

        return {"success": True, "conflict": False, "error": None, "output": None}

    except Exception as e:
        return {"success": False, "conflict": False, "error": str(e), "output": None}
    finally:
        if worktree_path:
            try:
                subprocess.run(
                    ["git", "-C", repo_dir, "worktree", "remove", "--force", worktree_path],
                    check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
            except Exception:
                pass
            shutil.rmtree(worktree_path, ignore_errors=True)


def cleanup_git_locks(repo_dir: str | None = None) -> dict:
    """Remove common git lock files (index.lock etc.) that block rebase/push/worktree ops after prior failures, unclean exits, or main/worktree collisions (addresses #514 incidents).

    Call before git operations in babysit local-rebase or any PR fix flow.

    Returns: {"cleaned": [removed paths], "errors": [error msgs]}

    Robust: safe if no locks or no repo.
    """
    if repo_dir is None:
        try:
            repo_dir = subprocess.check_output(
                ["git", "rev-parse", "--show-toplevel"], text=True, cwd="."
            ).strip()
        except Exception as e:
            return {"cleaned": [], "errors": [f"cannot detect repo_dir: {e}"]}

    locks = [os.path.join(repo_dir, ".git", "index.lock")]
    cleaned: list[str] = []
    errors: list[str] = []
    for lock_path in locks:
        if os.path.exists(lock_path):
            try:
                os.unlink(lock_path)
                cleaned.append(lock_path)
            except Exception as e:
                errors.append(f"{lock_path}: {e}")
    return {"cleaned": cleaned, "errors": errors}


def verify_worktree_is_isolated() -> dict:
    """Verification step recommended for all worktree use during babysit/fixes (addresses #514).

    Checks that current checkout appears to be an isolated worktree (not the main clone).
    Looks for typical signals from our flows (temp dirs, 'worktree' or 'plate-' in path).

    Returns: {"is_isolated": bool, "toplevel": str, "warning": str | None}
    Use in guidance/persona: always run `git rev-parse --show-toplevel` (or this helper) before edits/rebase in worktree; abort if not isolated.
    """
    try:
        toplevel = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"], text=True, cwd="."
        ).strip()
        is_isolated = (
            "worktree" in toplevel.lower()
            or "plate-" in toplevel
            or tempfile.gettempdir() in toplevel
            or "/tmp/" in toplevel
        )
        warning = None if is_isolated else "Current toplevel does not look like an isolated worktree (locks, wrong CWD, or main checkout risk). Use worktree for all PR changes/babysit local-rebase; verify before git ops."
        return {"is_isolated": is_isolated, "toplevel": toplevel, "warning": warning}
    except Exception as e:
        return {"is_isolated": False, "toplevel": "", "warning": f"git rev-parse --show-toplevel failed: {e}"}


def babysit_pr(
    pr_number: int,
    repo: str | None = None,
    *,
    agent_logins: str | None = None,
    act: bool = False,
    branch_update_strategy: str | None = None,
    pr_review_scope: str | None = None,
    client: GhClient | None = None,
) -> BabysitReport:
    """Babysit a pull request for actionable review feedback and base branch sync.

    Use get_pr_merge_gates for the comprehensive 'make this PR mergeable' helper (enumerates common gates like labels, CI, threads, etc., per #526).

    Args:
        pr_number: Pull request number
        repo: Repository identifier (owner/name), defaults to git remote
        agent_logins: Optional comma-separated allowlist of logins (overrides scope)
        act: If True, post trigger comments when issues detected and auto-resolve outdated threads
        branch_update_strategy: How to handle out-of-sync base branch.
            Options: "copilot-request" (default), "local-rebase", "none"
        pr_review_scope: ``all`` | ``bot-only`` | ``human-only`` (default from .plate or ``all``) (#496)
        client: Optional GitHub client

    Returns:
        BabysitReport with detection and action results
    """
    target = resolve_repo(repo)
    gh = client or GhClient()
    strategy = branch_update_strategy or _DEFAULT_STRATEGY
    scope = resolve_pr_review_scope(pr_review_scope)

    # Validate strategy
    if strategy not in _VALID_STRATEGIES:
        raise ValueError(f"Invalid branch_update_strategy: {strategy}. Must be one of {_VALID_STRATEGIES}")

    # Load PR data including threads and merge state
    pr_data = _load_pr_data(gh, target, pr_number)
    threads = pr_data.get("reviewThreads", [])
    actionable = _extract_actionable_threads(threads, agent_logins, scope=scope)

    # Detect base branch sync state
    sync_info = _detect_base_branch_out_of_sync(pr_data)

    # Handle review thread feedback
    posted = False
    trigger_url = None
    if act and actionable and not _has_existing_babysit_comment(gh, target, pr_number):
        trigger_url = _post_babysit_trigger(gh, target, pr_number, actionable, scope=scope)
        posted = True

    # #605: auto-resolve outdated unresolved threads when acting (post-fix state)
    auto_resolved_ids: list[str] = []
    auto_resolve_errors: list[str] = []
    if act:
        for item in _extract_outdated_unresolved_threads(threads):
            tid = item.get("thread_id")
            if not tid:
                continue
            try:
                result = resolve_review_thread(thread_id=tid, repo=target, client=gh)
                if result.get("resolved"):
                    auto_resolved_ids.append(tid)
                else:
                    auto_resolve_errors.append(f"{tid}: resolve returned resolved=false")
            except Exception as exc:  # noqa: BLE001 — best-effort; report errors, continue
                auto_resolve_errors.append(f"{tid}: {exc}")

    # Handle base branch sync
    merge_trigger_posted = False
    merge_trigger_url = None
    local_rebase_performed = False
    local_rebase_success = None
    local_rebase_conflict = False
    local_rebase_error = None
    if act and sync_info["out_of_sync"] and strategy == "copilot-request":
        if not _has_existing_merge_trigger_comment(gh, target, pr_number):
            merge_trigger_url = _post_merge_trigger(gh, target, pr_number, sync_info)
            merge_trigger_posted = True
    elif act and sync_info["out_of_sync"] and strategy == "local-rebase":
        # Pre-clean locks and verify isolation for robustness (#514)
        cleanup_git_locks()
        v = verify_worktree_is_isolated()
        rebase_res = _perform_local_rebase(sync_info.get("base_ref"), sync_info.get("head_ref"))
        local_rebase_performed = True
        local_rebase_success = rebase_res.get("success", False)
        local_rebase_conflict = rebase_res.get("conflict", False)
        local_rebase_error = rebase_res.get("error")
        # Note: we do not post copilot trigger when local-rebase is chosen

    suggestion_n = sum(1 for a in actionable if a.get("has_suggestion"))
    high_risk_n = sum(1 for a in actionable if a.get("high_risk_path") and a.get("has_suggestion"))
    summaries = [
        {
            "thread_id": a.get("thread_id"),
            "author": a.get("author"),
            "has_suggestion": a.get("has_suggestion"),
            "prefer_apply_suggestion": a.get("prefer_apply_suggestion"),
            "high_risk_path": a.get("high_risk_path"),
            "path": a.get("path"),
            "url": a.get("url"),
        }
        for a in actionable
    ]

    return BabysitReport(
        repo=target,
        pr_number=pr_number,
        detected_threads=len(threads),
        actionable_threads=len(actionable),
        trigger_comment_posted=posted,
        trigger_comment_url=trigger_url,
        out_of_sync=sync_info["out_of_sync"],
        merge_state=sync_info["state"],
        merge_trigger_posted=merge_trigger_posted,
        merge_trigger_url=merge_trigger_url,
        local_rebase_performed=local_rebase_performed,
        local_rebase_success=local_rebase_success,
        local_rebase_conflict=local_rebase_conflict,
        local_rebase_error=local_rebase_error,
        auto_resolved_threads=len(auto_resolved_ids),
        auto_resolved_thread_ids=auto_resolved_ids or None,
        auto_resolve_errors=auto_resolve_errors or None,
        pr_review_scope=scope,
        threads_with_suggestions=suggestion_n,
        high_risk_suggestion_threads=high_risk_n,
        actionable_thread_summaries=summaries or None,
    )


def resolve_review_thread(
    thread_id: str,
    repo: str | None = None,
    *,
    client: GhClient | None = None,
) -> dict:
    target = resolve_repo(repo)
    gh = client or GhClient()
    query = """
mutation($threadId: ID!) {
  resolveReviewThread(input: { threadId: $threadId }) {
    thread {
      id
      isResolved
    }
  }
}
""".strip()
    payload = gh.api(
        "graphql",
        method="POST",
        fields={"query": query, "threadId": thread_id},
    )
    thread = (
        ((payload or {}).get("data") or {})
        .get("resolveReviewThread", {})
        .get("thread", {})
    )
    return {"repo": target, "thread_id": thread.get("id", thread_id), "resolved": bool(thread.get("isResolved"))}


def get_actionable_review_threads(
    pr_number: int,
    repo: str | None = None,
    agent_logins: str | None = None,
    *,
    pr_review_scope: str | None = None,
    client: GhClient | None = None,
) -> list[dict]:
    """High-level encapsulated helper for listing actionable review threads.

    Returns list of dicts (thread_id, comment_id=databaseId, author, url, body, suggestion
    metadata) for unresolved, non-outdated threads in ``pr_review_scope`` (#496).

    Default scope is ``all`` (humans + bots including Copilot). Use ``bot-only`` for
    conservative bot-only filtering, or pass ``agent_logins`` as an explicit allowlist.

    Internally uses the exact GraphQL load (reviewThreads(first:100), comments, databaseId,
    author login) + extraction + filtering. Pagination stub (first:100 sufficient for typical
    PR feedback volume; extend with pageInfo cursors in future if >100 needed).

    **Agents must use this (or the counts/actionables from babysit_pr / get_pr_merge_gates)
    + resolve_review_thread (or the plate_pr_babysit + plate_resolve_review_thread MCP/CLI surfaces)
    instead of any raw GraphQL, jq, mktemp, sed, NO_COLOR=1, or manual mutation construction.**
    This fully addresses #516 (encapsulation of review thread handling).

    See pr-babysit docstring, agent_guidance QUIET_OPERATIONS_GUIDANCE (Full PR Green), and
    AGENTS.md babysit section.
    """
    target = resolve_repo(repo)
    gh = client or GhClient()
    pr_data = _load_pr_data(gh, target, pr_number)
    threads = pr_data.get("reviewThreads", [])
    scope = resolve_pr_review_scope(pr_review_scope)
    return _extract_actionable_threads(threads, agent_logins, scope=scope)


def get_pr_merge_gates(pr_number: int, repo: str | None = None, *, client: GhClient | None = None) -> dict:
    """Helper in the pr-babysit skill (or small procedure) to enumerate and address common merge gates for a comprehensive 'make this PR mergeable' operation.

    This addresses the core issue in #526: instead of sequential single fixes, use this to inspect all at once.

    Common gates (from PLATE + GitHub):
    - Labels (type like Bug/Feature, area:*, risk:*, Epic: if applicable)
    - Merge state / base sync (BEHIND/CONFLICTING/DIRTY -> use babysit rebase or copilot-request)
    - Feedback-resolution: unresolved review threads (esp. from agents) -> use plate_pr_babysit + resolve
    - CI/test jobs, title check, issue-link check, feature-change-files (fragments), audit, deploy, etc.
    - Other: documentation gate if applicable.

    Usage (agent procedure):
    1. Call plate_pr_babysit (or this if exposed) + gh pr checks <N> + gh issue view <N> for labels.
    2. Fix what you can in worktree (rebase, labels via gh pr edit, resolve threads, apply suggestions, fix tests).
    3. Push once (or minimal).
    4. Re-inspect all.
    5. Repeat until only human items (e.g. actual CHANGES_REQUESTED from owner, high-risk) remain.
    6. Report one-sentence summary of remaining.

    See Full PR Green / Make Mergeable Loop in agent_guidance.py QUIET_OPERATIONS_GUIDANCE, the checklist in AGENTS.md babysit section, and persona example.

    Returns dict with key statuses from babysit logic + note on full checklist.
    """
    target = resolve_repo(repo)
    gh = client or GhClient()
    pr_data = _load_pr_data(gh, target, pr_number)
    sync_info = _detect_base_branch_out_of_sync(pr_data)
    threads = pr_data.get("reviewThreads", [])
    scope = resolve_pr_review_scope(None)
    actionable = _extract_actionable_threads(threads, None, scope=scope)
    ci = _summarize_status_check_rollup(pr_data.get("statusCheckRollup"))
    review_decision = pr_data.get("reviewDecision")
    gate_eval = evaluate_babysit_gates(
        {
            "merge_state": sync_info.get("state"),
            "unresolved_review_threads": len(
                [t for t in threads if not t.get("isResolved") and not t.get("isOutdated")]
            ),
            "actionable_agent_threads": len(actionable),
            "review_decision": review_decision,
            **ci,
        }
    )

    return {
        "repo": target,
        "pr_number": pr_number,
        "merge_state": sync_info.get("state"),
        "out_of_sync": sync_info.get("out_of_sync"),
        "unresolved_review_threads": len(
            [t for t in threads if not t.get("isResolved") and not t.get("isOutdated")]
        ),
        "actionable_agent_threads": len(actionable),
        "pr_review_scope": scope,
        "threads_with_suggestions": sum(1 for a in actionable if a.get("has_suggestion")),
        "review_decision": review_decision,
        "ci_state": ci.get("ci_state"),
        "failing_checks": ci.get("failing_checks", 0),
        "pending_checks": ci.get("pending_checks", 0),
        "ci_failing": ci.get("ci_failing", False),
        "ci_pending": ci.get("ci_pending", False),
        "loop_advance_blocked": gate_eval.get("blocked", False),
        "loop_advance_reason": gate_eval.get("reason"),
        "note": "Use plate_pr_babysit + gh pr checks + gh issue view for full gates (labels, CI, title, docs, etc.). Default pr_review_scope=all (#496) so Copilot/human threads count. Bug/feature loops use evaluate_babysit_gates (CI + review_decision + threads + merge_state). Fix comprehensively in one loop. Escalate only true human-judgment items with need:human-review.",
    }
