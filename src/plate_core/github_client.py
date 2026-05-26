"""Small GitHub client wrapper backed by `gh api`."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass


class GhApiError(RuntimeError):
    """Raised when a `gh api` call fails."""


@dataclass
class GhClient:
    """Minimal GitHub API helper using the authenticated `gh` CLI."""

    def api(self, endpoint: str, method: str = "GET", fields: dict | None = None) -> object:
        cmd = ["gh", "api", endpoint]
        if method != "GET":
            cmd.extend(["-X", method])
        for key, value in (fields or {}).items():
            cmd.extend(["-F", f"{key}={value}"])
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if proc.returncode != 0:
            raise GhApiError(proc.stderr.strip() or proc.stdout.strip() or "gh api call failed")
        out = proc.stdout.strip()
        return json.loads(out) if out else {}
