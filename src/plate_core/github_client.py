"""Small GitHub client wrapper backed by `gh api`."""

from __future__ import annotations

import json
import random
import re
import subprocess
import time
from dataclasses import dataclass


class GhApiError(RuntimeError):
    """Raised when a `gh api` call fails."""


def _sanitize_error(msg: str) -> str:
    """Redact potential secrets/tokens from error messages (secret-safety for #270)."""
    # Redact common token patterns (ghp_, gho_, bearer, etc.) and any long hex-ish that might be token
    msg = re.sub(r"(ghp_|gho_|ghs_|ghr_|Bearer\s+|token=)[A-Za-z0-9_\-]+", r"\1[REDACTED]", msg, flags=re.IGNORECASE)
    msg = re.sub(r"([A-Za-z0-9_\-]{20,})", "[REDACTED]", msg)  # fallback for long tokens
    return msg


@dataclass
class GhClient:
    """Minimal GitHub API helper using the authenticated `gh` CLI.

    Enhanced for beta: retries with backoff/jitter for transient errors (rate limits,
    5xx, timeouts), rate-limit awareness (sleep on detected limit), secret redaction
    in errors. Supports partial resilience for autonomous tools (babysit, health, etc.).
    """

    def api(
        self,
        endpoint: str,
        method: str = "GET",
        fields: dict | None = None,
        retries: int = 3,
        base_backoff: float = 0.5,
    ) -> object:
        """Execute gh api call with resilience.

        retries: max attempts (default 3 for rate/transient tolerance).
        base_backoff: seconds base for exp backoff + jitter.
        """
        cmd = ["gh", "api", endpoint]
        if method != "GET":
            cmd.extend(["-X", method])
        for key, value in (fields or {}).items():
            if isinstance(value, bool):
                cmd.extend(["-F", f"{key}={'true' if value else 'false'}"])
            elif isinstance(value, (int, float)):
                cmd.extend(["-F", f"{key}={value}"])
            elif isinstance(value, (list, tuple)):
                for item in value:
                    if isinstance(item, bool):
                        cmd.extend(["-F", f"{key}[]={'true' if item else 'false'}"])
                    elif isinstance(item, (int, float)):
                        cmd.extend(["-F", f"{key}[]={item}"])
                    else:
                        cmd.extend(["-f", f"{key}[]={item}"])
            else:
                cmd.extend(["-f", f"{key}={value}"])

        last_err = None
        for attempt in range(retries):
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
            if proc.returncode == 0:
                out = proc.stdout.strip()
                return json.loads(out) if out else {}

            err = proc.stderr.strip() or proc.stdout.strip() or "gh api call failed"
            safe_err = _sanitize_error(err)
            last_err = GhApiError(safe_err)

            # Rate limit or transient? sleep and retry
            lower = err.lower()
            is_rate = "rate limit" in lower or "403" in lower and "limit" in lower
            is_transient = is_rate or "5" in str(proc.returncode) or "timeout" in lower or "connection" in lower or "temporar" in lower

            if attempt < retries - 1 and is_transient:
                # Exp backoff + jitter
                sleep = base_backoff * (2 ** attempt) + random.uniform(0, 0.3)
                if is_rate:
                    # Try to be nicer on rate
                    sleep = max(sleep, 2.0)
                time.sleep(sleep)
                continue
            else:
                break

        raise last_err or GhApiError("gh api call failed after retries")

    # --- Discussions support (Feature #329) ---
    # Uses REST for list/get/comments (category/state filtering done caller-side for flexibility)
    # Uses GraphQL for categories + createDiscussion (no direct REST create observed; requires repo ID + category ID)

    def list_discussions(self, owner: str, repo: str, **params: object) -> list[dict]:
        """List discussions for a repo. Pass per_page, page, state etc as kwargs (filtered client-side often)."""
        endpoint = f"repos/{owner}/{repo}/discussions"
        return self.api(endpoint, fields=params) or []

    def get_discussion(self, owner: str, repo: str, number: int) -> dict:
        endpoint = f"repos/{owner}/{repo}/discussions/{number}"
        return self.api(endpoint) or {}

    def list_discussion_comments(self, owner: str, repo: str, number: int, **params: object) -> list[dict]:
        endpoint = f"repos/{owner}/{repo}/discussions/{number}/comments"
        return self.api(endpoint, fields=params) or []

    def add_discussion_comment(self, owner: str, repo: str, number: int, body: str) -> dict:
        endpoint = f"repos/{owner}/{repo}/discussions/{number}/comments"
        return self.api(endpoint, method="POST", fields={"body": body}) or {}

    def list_discussion_categories(self, owner: str, repo: str) -> list[dict]:
        """Return categories via GraphQL (name, slug, id, etc.)."""
        query = """
        query($owner: String!, $name: String!) {
          repository(owner: $owner, name: $name) {
            discussionCategories(first: 20) {
              nodes { id name slug emoji description isAnswerable }
            }
          }
        }
        """
        payload = self.api(
            "graphql", method="POST", fields={"query": query, "owner": owner, "name": repo}
        ) or {}
        return (
            (payload.get("data") or {})
            .get("repository", {})
            .get("discussionCategories", {})
            .get("nodes", [])
        )

    def create_discussion(self, owner: str, repo: str, category_id: str, title: str, body: str) -> dict:
        """Create via GraphQL mutation. Caller must provide valid category node ID (from list_discussion_categories)."""
        # Resolve repo database ID
        repo_q = """
        query($owner: String!, $name: String!) { repository(owner:$owner, name:$name) { id } }
        """
        rdata = self.api("graphql", method="POST", fields={"query": repo_q, "owner": owner, "name": repo}) or {}
        repo_id = (rdata.get("data") or {}).get("repository", {}).get("id")
        if not repo_id:
            raise GhApiError("Could not resolve repository database ID for createDiscussion")

        mutation = """
        mutation($repositoryId: ID!, $categoryId: ID!, $title: String!, $body: String!) {
          createDiscussion(input: {repositoryId: $repositoryId, categoryId: $categoryId, title: $title, body: $body}) {
            discussion { id number title url category { id name slug } }
          }
        }
        """
        payload = self.api(
            "graphql",
            method="POST",
            fields={
                "query": mutation,
                "repositoryId": repo_id,
                "categoryId": category_id,
                "title": title,
                "body": body,
            },
        ) or {}
        return (payload.get("data") or {}).get("createDiscussion", {}).get("discussion", {}) or {}
