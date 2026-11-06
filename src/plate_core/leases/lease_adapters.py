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


def _write_all(fd: int, data: bytes) -> None:
    """Write every byte (``os.write`` may short-write on some paths)."""

    view = memoryview(data)
    offset = 0
    total = len(data)
    while offset < total:
        n = os.write(fd, view[offset:])
        if n is None or n <= 0:
            raise OSError(f"os.write returned non-positive length: {n!r}")
        offset += n


def _unlink_quiet(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        try:
            if path.is_file():
                path.unlink()
        except OSError:
            pass


def _validate_active_record(active: dict[str, Any]) -> bool:
    """Return True when ``active`` looks like a live lockfile lease record."""

    try:
        if str(active.get("lease_id", "")).strip() == "":
            return False
        if str(active.get("idempotency_key", "")).strip() == "":
            return False
        if str(active.get("requester", "")).strip() == "":
            return False
        exp = float(active.get("expires_at", 0.0))
    except (TypeError, ValueError):
        return False
    return exp > 0.0


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

    def _read_state(self) -> tuple[dict[str, Any], str]:
        """Return ``(state, integrity)`` where integrity is ok|missing|corrupt.

        **Corrupt** means the file exists but is not usable JSON with a sane shape.
        Callers must not treat that as a free slot — that would double-grant capacity.
        """

        if not self._state_path.is_file():
            return {"active": None}, "missing"
        try:
            raw = self._state_path.read_text(encoding="utf-8")
        except OSError:
            return {"active": None, "state_integrity": "corrupt"}, "corrupt"
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return {"active": None, "state_integrity": "corrupt"}, "corrupt"
        if not isinstance(data, dict):
            return {"active": None, "state_integrity": "corrupt"}, "corrupt"
        active = data.get("active")
        if active is None:
            return data, "ok"
        if isinstance(active, dict):
            now = time.time()
            if _validate_active_record(active):
                if self._active_expired(active, now):
                    cleaned = dict(data)
                    cleaned["active"] = None
                    return cleaned, "ok"
                return data, "ok"
            return {"active": None, "state_integrity": "corrupt"}, "corrupt"
        return {"active": None, "state_integrity": "corrupt"}, "corrupt"

    def _write_state_atomic(self, state: dict[str, Any]) -> None:
        tmp = self._state_path.with_suffix(".json.tmp")
        payload = json.dumps(state, indent=2, sort_keys=True) + "\n"
        encoded = payload.encode("utf-8")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            _write_all(fd, encoded)
            os.fsync(fd)
        except OSError:
            try:
                os.close(fd)
            except OSError:
                pass
            _unlink_quiet(tmp)
            raise
        try:
            os.close(fd)
        except OSError:
            _unlink_quiet(tmp)
            raise
        try:
            os.replace(tmp, self._state_path)
        except OSError:
            _unlink_quiet(tmp)
            raise

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
            state, integrity = self._read_state()
            if integrity == "corrupt":
                return LeaseAcquireResult(status="wait", wait_seconds=300)
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
            try:
                self._write_state_atomic(state)
            except OSError:
                return LeaseAcquireResult(status="wait", wait_seconds=300)
            return LeaseAcquireResult(status="granted", lease_id=lease_id)

    def renew(self, *, lease_id: str, requester: str) -> LeaseRenewResult:
        now = time.time()
        with self._with_mutex():
            state, integrity = self._read_state()
            if integrity == "corrupt":
                return LeaseRenewResult(status="not_found")
            active = state.get("active")
            if not isinstance(active, dict):
                return LeaseRenewResult(status="not_found")
            if str(active.get("lease_id")) != lease_id:
                return LeaseRenewResult(status="revoked")
            if active.get("requester") != requester:
                return LeaseRenewResult(status="revoked")
            if self._active_expired(active, now):
                state["active"] = None
                try:
                    self._write_state_atomic(state)
                except OSError:
                    return LeaseRenewResult(status="not_found")
                return LeaseRenewResult(status="expired")
            active["expires_at"] = now + float(self._ttl_s)
            state["active"] = active
            try:
                self._write_state_atomic(state)
            except OSError:
                return LeaseRenewResult(status="not_found")
            return LeaseRenewResult(status="ok")

    def release(
        self,
        *,
        lease_id: str,
        requester: str,
        left_running: bool,
        notes: str,
    ) -> None:
        with self._with_mutex():
            state, integrity = self._read_state()
            if integrity == "corrupt":
                return
            active = state.get("active")
            if (
                isinstance(active, dict)
                and str(active.get("lease_id")) == lease_id
                and active.get("requester") == requester
            ):
                state["active"] = None
                state["last_release"] = {
                    "lease_id": lease_id,
                    "requester": requester,
                    "left_running": bool(left_running),
                    "notes": str(notes),
                    "released_at": time.time(),
                }
                try:
                    self._write_state_atomic(state)
                except OSError:
                    return

    def list_by_requester(self, requester: str) -> list[LeaseRecord]:
        now = time.time()
        with self._with_mutex():
            state, integrity = self._read_state()
            if integrity == "corrupt":
                return []
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
