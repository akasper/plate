"""Pluggable capacity lease adapters: local (always-grant) and lockfile (#1427)."""

from __future__ import annotations

import json
import os
import secrets
import threading
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

try:
    import fcntl
except ImportError:  # pragma: no cover — non-Unix; tests run on Linux
    fcntl = None  # type: ignore[assignment]

from .types import (
    LeaseAcquireResult,
    LeaseRecord,
    LeaseRenewResult,
    LeaseTags,
)


class LeaseAdapter(ABC):
    """Capacity lease port (Lull contract; exclusivity remains with the claim)."""

    @abstractmethod
    def acquire(
        self,
        *,
        idempotency_key: str,
        requester: str,
        tags: LeaseTags,
        claim_oid: str | None,
        wait_seconds: int,
    ) -> LeaseAcquireResult:
        """Acquire or return an existing grant for ``idempotency_key``.

        ``wait_seconds`` is the caller's long-poll budget (hub: ≤300). ``lockfile``
        may ignore it and return immediately with ``wait`` when the slot is busy.
        """

    @abstractmethod
    def renew(self, *, lease_id: str, requester: str) -> LeaseRenewResult:
        """Renew an active lease (caller should poll every ttl/3)."""

    @abstractmethod
    def release(
        self,
        *,
        lease_id: str,
        requester: str,
        left_running: bool,
        notes: str,
    ) -> None:
        """Release a lease; record structured notes for forensics."""

    @abstractmethod
    def list_by_requester(self, requester: str) -> list[LeaseRecord]:
        """List non-expired leases held by ``requester`` (crash recovery)."""


def _lease_tags_to_json(tags: LeaseTags) -> dict[str, Any]:
    return {
        "repo": tags.repo,
        "issue": tags.issue,
        "state": tags.state,
        "transition_id": tags.transition_id,
        "tier": tags.tier,
        "budget": dict(tags.budget),
    }


def _lease_tags_from_json(data: dict[str, Any]) -> LeaseTags:
    return LeaseTags(
        repo=str(data.get("repo", "")),
        issue=str(data.get("issue", "")),
        state=str(data.get("state", "")),
        transition_id=str(data.get("transition_id", "")),
        tier=str(data.get("tier", "")),
        budget=dict(data.get("budget") or {}),
    )


class LocalLeaseAdapter(LeaseAdapter):
    """Always grants; records leases in memory (no capacity enforcement)."""

    def __init__(self, ttl_s: int) -> None:
        self._ttl_s = ttl_s
        self._lock = threading.Lock()
        self._by_id: dict[str, LeaseRecord] = {}
        self._by_key: dict[str, str] = {}

    def acquire(
        self,
        *,
        idempotency_key: str,
        requester: str,
        tags: LeaseTags,
        claim_oid: str | None,
        wait_seconds: int,
    ) -> LeaseAcquireResult:
        del wait_seconds  # local adapter never waits
        with self._lock:
            existing_id = self._by_key.get(idempotency_key)
            if existing_id:
                rec = self._by_id[existing_id]
                return LeaseAcquireResult(status="granted", lease_id=rec.lease_id)
            lease_id = f"llocal_{secrets.token_hex(8)}"
            rec = LeaseRecord(
                lease_id=lease_id,
                idempotency_key=idempotency_key,
                requester=requester,
                tags=tags,
                claim_oid=claim_oid,
            )
            self._by_id[lease_id] = rec
            self._by_key[idempotency_key] = lease_id
            return LeaseAcquireResult(status="granted", lease_id=lease_id)

    def renew(self, *, lease_id: str, requester: str) -> LeaseRenewResult:
        with self._lock:
            rec = self._by_id.get(lease_id)
            if rec is None:
                return LeaseRenewResult(status="not_found")
            if rec.requester != requester:
                return LeaseRenewResult(status="revoked")
            return LeaseRenewResult(status="ok")

    def release(
        self,
        *,
        lease_id: str,
        requester: str,
        left_running: bool,
        notes: str,
    ) -> None:
        del left_running, notes
        with self._lock:
            rec = self._by_id.get(lease_id)
            if rec is None:
                return
            if rec.requester != requester:
                return
            self._by_id.pop(lease_id, None)
            if self._by_key.get(rec.idempotency_key) == lease_id:
                self._by_key.pop(rec.idempotency_key, None)

    def list_by_requester(self, requester: str) -> list[LeaseRecord]:
        with self._lock:
            return [row for row in self._by_id.values() if row.requester == requester]


class LockfileLeaseAdapter(LeaseAdapter):
    """Single-machine mutex + JSON state; safe across processes (fcntl + atomic rename)."""

    def __init__(self, lock_dir: Path | str, ttl_s: int) -> None:
        if fcntl is None:
            raise RuntimeError("LockfileLeaseAdapter requires fcntl (Unix)")
        self._dir = Path(lock_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._ttl_s = ttl_s
        self._mutex_path = self._dir / "leases.mutex"
        self._state_path = self._dir / "leases_state.json"

    def _with_mutex(self) -> "_Mutex":
        return _Mutex(self._mutex_path)

    def _read_state(self) -> dict[str, Any]:
        if not self._state_path.is_file():
            return {"active": None}
        try:
            data = json.loads(self._state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"active": None}
        if not isinstance(data, dict):
            return {"active": None}
        return data

    def _write_state_atomic(self, state: dict[str, Any]) -> None:
        tmp = self._state_path.with_suffix(".json.tmp")
        payload = json.dumps(state, indent=2, sort_keys=True) + "\n"
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            os.write(fd, payload.encode("utf-8"))
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(tmp, self._state_path)

    def _active_expired(self, active: dict[str, Any], now: float) -> bool:
        exp = float(active.get("expires_at", 0.0))
        return now >= exp

    def acquire(
        self,
        *,
        idempotency_key: str,
        requester: str,
        tags: LeaseTags,
        claim_oid: str | None,
        wait_seconds: int,
    ) -> LeaseAcquireResult:
        del wait_seconds
        now = time.time()
        with self._with_mutex():
            state = self._read_state()
            active = state.get("active")
            if isinstance(active, dict) and not self._active_expired(active, now):
                if active.get("idempotency_key") == idempotency_key:
                    return LeaseAcquireResult(status="granted", lease_id=str(active["lease_id"]))
                return LeaseAcquireResult(status="wait", wait_seconds=300)
            # Stale / empty slot — grant
            lease_id = f"lfile_{secrets.token_hex(8)}"
            record = {
                "lease_id": lease_id,
                "idempotency_key": idempotency_key,
                "requester": requester,
                "claim_oid": claim_oid,
                "tags": _lease_tags_to_json(tags),
                "expires_at": now + float(self._ttl_s),
            }
            state["active"] = record
            self._write_state_atomic(state)
            return LeaseAcquireResult(status="granted", lease_id=lease_id)

    def renew(self, *, lease_id: str, requester: str) -> LeaseRenewResult:
        now = time.time()
        with self._with_mutex():
            state = self._read_state()
            active = state.get("active")
            if not isinstance(active, dict):
                return LeaseRenewResult(status="not_found")
            if str(active.get("lease_id")) != lease_id:
                return LeaseRenewResult(status="revoked")
            if active.get("requester") != requester:
                return LeaseRenewResult(status="revoked")
            if self._active_expired(active, now):
                state["active"] = None
                self._write_state_atomic(state)
                return LeaseRenewResult(status="expired")
            active["expires_at"] = now + float(self._ttl_s)
            state["active"] = active
            self._write_state_atomic(state)
            return LeaseRenewResult(status="ok")

    def release(
        self,
        *,
        lease_id: str,
        requester: str,
        left_running: bool,
        notes: str,
    ) -> None:
        del left_running, notes
        with self._with_mutex():
            state = self._read_state()
            active = state.get("active")
            if (
                isinstance(active, dict)
                and str(active.get("lease_id")) == lease_id
                and active.get("requester") == requester
            ):
                state["active"] = None
                self._write_state_atomic(state)

    def list_by_requester(self, requester: str) -> list[LeaseRecord]:
        now = time.time()
        with self._with_mutex():
            state = self._read_state()
            active = state.get("active")
            if not isinstance(active, dict):
                return []
            if self._active_expired(active, now):
                return []
            if active.get("requester") != requester:
                return []
            tags = _lease_tags_from_json(dict(active.get("tags") or {}))
            return [
                LeaseRecord(
                    lease_id=str(active["lease_id"]),
                    idempotency_key=str(active["idempotency_key"]),
                    requester=str(active["requester"]),
                    tags=tags,
                    claim_oid=active.get("claim_oid"),
                )
            ]


class _Mutex:
    """POSIX advisory lock around mutating the lease state file."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._fh: Any = None

    def __enter__(self) -> _Mutex:
        self._fh = open(self._path, "a+b")
        fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._fh is not None:
            fh = self._fh
            self._fh = None
            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
            finally:
                fh.close()
        return None


def max_lease_runover_seconds(ttl_s: int, grace_s: int) -> int:
    """Worst-case overrun after a failed renew: ``ttl_s``/3 + ``grace_s`` (Lull contract)."""

    return ttl_s // 3 + grace_s


def recover_lease_or_release(
    adapter: LeaseAdapter,
    *,
    lease_id: str,
    requester: str,
    marker_claim_oid: str | None,
    left_running: bool = False,
    notes: str = "crash recovery: claim oid mismatch",
) -> str:
    """Resume only when the marker's lease id and claim oid match; otherwise release.

    Returns ``\"resume\"`` when a matching active lease is listed, ``\"released\"`` when the
    listed lease disagrees with ``marker_claim_oid`` and was released, or ``\"absent\"``
    when no such lease is visible for ``requester``.
    """

    for rec in adapter.list_by_requester(requester):
        if rec.lease_id != lease_id:
            continue
        if rec.claim_oid == marker_claim_oid:
            return "resume"
        adapter.release(
            lease_id=lease_id,
            requester=requester,
            left_running=left_running,
            notes=notes,
        )
        return "released"
    return "absent"


def lease_adapter_from_config(
    cfg: dict[str, Any],
    *,
    lock_dir: Path | str | None = None,
) -> LeaseAdapter:
    """Factory: ``leases.adapter`` is ``local`` or ``lockfile``."""

    merged = dict(cfg)
    name = str(merged.get("adapter", "local")).strip().lower()
    ttl_s = int(merged.get("ttl_s", 600))
    if name == "local":
        return LocalLeaseAdapter(ttl_s=ttl_s)
    if name == "lockfile":
        if lock_dir is None:
            raise ValueError("lockfile adapter requires lock_dir=")
        return LockfileLeaseAdapter(lock_dir, ttl_s=ttl_s)
    raise ValueError(f"unknown leases.adapter: {name!r}")
