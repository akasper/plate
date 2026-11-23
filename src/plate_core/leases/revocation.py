"""Helpers for revoked renewals and ``revocations_before_human`` (#1427)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

Outcome = Literal["requeue", "needs_human"]


@dataclass
class RevocationLedger:
    """Counts revoked renewals per supervising *requester* (process identity).

    This is an in-memory helper for a single PLATE supervisor process. Multiple
    unsynchronized threads sharing one ledger should use an external lock; separate
    processes need a persisted counter (out of scope for #1427).
    """

    threshold: int
    counts: dict[str, int] = field(default_factory=dict)

    def note_revoked_renew(
        self,
        requester: str,
        *,
        rollback_reservation: Callable[[], None],
        requeue: Callable[[], None],
    ) -> Outcome:
        """Apply rollback + requeue, bump count, return ``needs_human`` at threshold.

        Per design: after ``revocations_before_human`` revoked renewals, escalate.
        """

        rollback_reservation()
        requeue()
        n = self.counts.get(requester, 0) + 1
        self.counts[requester] = n
        if n >= self.threshold:
            return "needs_human"
        return "requeue"
