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

    def api(self, endpoint: str) -> object:
        proc = subprocess.run(
            ["gh", "api", endpoint],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            raise GhApiError(proc.stderr.strip() or proc.stdout.strip() or "gh api call failed")
        return json.loads(proc.stdout)

