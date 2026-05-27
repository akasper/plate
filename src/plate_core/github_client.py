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
            # Use -F (typed inference) only for native Python types that gh can safely coerce.
            # Strings use -f to prevent mis-parsing (e.g. "5319e7" as scientific notation).
            if isinstance(value, bool):
                cmd.extend(["-F", f"{key}={'true' if value else 'false'}"])
            elif isinstance(value, (int, float)):
                cmd.extend(["-F", f"{key}={value}"])
            else:
                cmd.extend(["-f", f"{key}={value}"])
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
