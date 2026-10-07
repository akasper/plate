"""Exponential backoff and stop conditions for PR babysit --watch (#1079).

Wiring into the watch loop lands in a follow-up PR; this module is pure logic
with injectable clocks for tests.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol


class WatchClock(Protocol):
    """Injectable time source for watch loops."""

    def now(self) -> datetime:
        """Return the current instant (timezone-aware)."""

    def sleep(self, seconds: float) -> None:
        """Block for ``seconds`` (real or simulated)."""


@dataclass
class SystemWatchClock:
    """Production clock using ``time.sleep`` and UTC ``datetime.now``."""

    def now(self) -> datetime:
        return datetime.now(timezone.utc)

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


@dataclass
class Backoff:
    """Exponential poll interval: quiet ticks grow, activity resets to ``min_interval``."""

    min_interval: int = 60
    max_interval: int = 1800
    factor: float = 2.0
    _next_quiet: int = field(default=0, init=False, repr=False)

    def __post_init__(self) -> None:
        self._next_quiet = self.min_interval

    def next_interval(self, changed: bool) -> int:
        """Return seconds to wait before the next poll.

        After ``changed`` is true, the interval resets to ``min_interval``.
        Each quiet tick (``changed`` false) returns the current interval then
        multiplies it by ``factor`` up to ``max_interval``.
        """
        if changed:
            self._next_quiet = self.min_interval
            return self.min_interval
        interval = self._next_quiet
        doubled = int(interval * self.factor)
        self._next_quiet = min(doubled, self.max_interval)
        return interval


def _pr_merged(pr: dict[str, Any]) -> bool:
    if pr.get("merged") is True:
        return True
    state = pr.get("state")
    if isinstance(state, str) and state.upper() == "MERGED":
        return True
    if pr.get("mergedAt"):
        return True
    return False


def _pr_closed_unmerged(pr: dict[str, Any]) -> bool:
    if _pr_merged(pr):
        return False
    state = pr.get("state")
    if isinstance(state, str):
        upper = state.upper()
        if upper == "CLOSED":
            return True
    if pr.get("closed") is True:
        return True
    if pr.get("closedAt"):
        return True
    return False


def should_stop(
    pr: dict[str, Any],
    started_at: datetime,
    now: datetime,
    max_hours: float,
) -> str | None:
    """Return a stop reason when the watch should end, else ``None``.

    Reasons: ``"merged"``, ``"closed"``, ``"max_hours_exceeded"``.
    """
    if _pr_merged(pr):
        return "merged"
    if _pr_closed_unmerged(pr):
        return "closed"
    if max_hours > 0:
        elapsed_hours = (now - started_at).total_seconds() / 3600.0
        if elapsed_hours > max_hours:
            return "max_hours_exceeded"
    return None
