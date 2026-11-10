"""Shared types for capacity lease adapters (Lull contract, #1427)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

AcquireStatus = Literal["granted", "wait", "needs_human"]
RenewStatus = Literal["ok", "revoked", "expired", "not_found"]


@dataclass(frozen=True)
class LeaseTags:
    """Tags recorded with every lease (opaque ``budget`` except for presence)."""

    repo: str
    issue: str
    state: str
    transition_id: str
    tier: str
    budget: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LeaseAcquireResult:
    status: AcquireStatus
    lease_id: str | None = None
    """When ``status == wait``, seconds to sleep before retry (hub / long-poll; capped ≤300)."""

    wait_seconds: int | None = None


@dataclass(frozen=True)
class LeaseRenewResult:
    status: RenewStatus


@dataclass(frozen=True)
class LeaseRecord:
    lease_id: str
    idempotency_key: str
    requester: str
    tags: LeaseTags
    claim_oid: str | None = None
