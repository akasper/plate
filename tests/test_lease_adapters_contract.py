"""Contract tests for lease adapters (#1427)."""

from __future__ import annotations

import multiprocessing
import os
import tempfile
import unittest
from collections import defaultdict
from pathlib import Path
from unittest.mock import Mock

from plate_core.leases import (
    LeaseAdapter,
    LeaseTags,
    LocalLeaseAdapter,
    LockfileLeaseAdapter,
    RevocationLedger,
    lease_adapter_from_config,
    max_lease_runover_seconds,
    recover_lease_or_release,
)
from plate_core.process_config import (
    DEFAULT_LEASES_CONFIG,
    load_merged_process_config,
    merge_process_config_with_defaults,
    normalize_leases_config,
)

_TAGS = lambda: LeaseTags(
    repo="test-org/test-repo",
    issue="1427",
    state="in_progress",
    transition_id="tr_1",
    tier="T1",
    budget={"allocation_usd": 10},
)


class LeaseAdapterContractTests:
    """Mixin: same assertions for each adapter via ``_make_adapter``."""

    _make_adapter: staticmethod

    def test_local_adapter_always_grants_and_records(self) -> None:
        ad = self._make_adapter()
        tags = _TAGS()
        ar = ad.acquire(
            idempotency_key="idem_1",
            requester="proc-a",
            tags=tags,
            claim_oid="oid_a",
            wait_seconds=0,
        )
        self.assertEqual(ar.status, "granted")
        self.assertIsNotNone(ar.lease_id)
        recs = ad.list_by_requester("proc-a")
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0].idempotency_key, "idem_1")
        self.assertEqual(recs[0].tags.repo, tags.repo)

    def test_acquire_idempotent_on_retry(self) -> None:
        ad = self._make_adapter()
        tags = _TAGS()
        a1 = ad.acquire(
            idempotency_key="idem_idem",
            requester="p",
            tags=tags,
            claim_oid="c1",
            wait_seconds=0,
        )
        a2 = ad.acquire(
            idempotency_key="idem_idem",
            requester="p",
            tags=tags,
            claim_oid="c2",
            wait_seconds=0,
        )
        self.assertEqual(a1.status, "granted")
        self.assertEqual(a2.status, "granted")
        self.assertEqual(a1.lease_id, a2.lease_id)

    def test_revoked_renew_rolls_back_and_requeue(self) -> None:
        ad = self._make_adapter()
        tags = _TAGS()
        ac = ad.acquire(
            idempotency_key="rk",
            requester="owner",
            tags=tags,
            claim_oid="co",
            wait_seconds=0,
        )
        self.assertIsNotNone(ac.lease_id)
        lease_id = ac.lease_id
        self.assertEqual(ad.renew(lease_id=lease_id, requester="owner").status, "ok")

        rb = Mock()
        rq = Mock()
        rr = ad.renew(lease_id=lease_id, requester="attacker")
        self.assertEqual(rr.status, "revoked")

        ledger = RevocationLedger(threshold=10)
        outcome = ledger.note_revoked_renew(
            "owner",
            rollback_reservation=rb,
            requeue=rq,
        )
        self.assertEqual(outcome, "requeue")
        rb.assert_called_once()
        rq.assert_called_once()

    def test_three_revocations_go_to_needs_human(self) -> None:
        ledger = RevocationLedger(threshold=3)
        noop = Mock()
        counts: defaultdict[str, int] = defaultdict(int)

        def rq() -> None:
            counts["n"] += 1

        for i in range(2):
            o = ledger.note_revoked_renew(
                "req",
                rollback_reservation=noop,
                requeue=rq,
            )
            self.assertEqual(o, "requeue", msg=f"iteration {i}")
        o3 = ledger.note_revoked_renew(
            "req",
            rollback_reservation=noop,
            requeue=rq,
        )
        self.assertEqual(o3, "needs_human")
        self.assertEqual(counts["n"], 3)

    def test_recovery_releases_mismatched_lease(self) -> None:
        ad = self._make_adapter()
        tags = _TAGS()
        ac = ad.acquire(
            idempotency_key="rc",
            requester="r",
            tags=tags,
            claim_oid="marker_oid_good",
            wait_seconds=0,
        )
        lid = ac.lease_id
        self.assertIsNotNone(lid)
        self.assertEqual(
            recover_lease_or_release(
                ad,
                lease_id=lid,
                requester="r",
                marker_claim_oid="marker_oid_good",
            ),
            "resume",
        )
        self.assertEqual(
            recover_lease_or_release(
                ad,
                lease_id=lid,
                requester="r",
                marker_claim_oid="stale_oid",
            ),
            "released",
        )
        self.assertEqual(ad.list_by_requester("r"), [])


class TestLocalAdapterContract(LeaseAdapterContractTests, unittest.TestCase):
    @staticmethod
    def _make_adapter() -> LeaseAdapter:
        return LocalLeaseAdapter(ttl_s=600)


class TestLockfileAdapterContract(LeaseAdapterContractTests, unittest.TestCase):
    @staticmethod
    def _make_adapter() -> LeaseAdapter:
        tmp = tempfile.mkdtemp()
        return LockfileLeaseAdapter(Path(tmp) / "z", ttl_s=600)

    def test_lockfile_adapter_exclusive_across_processes(self) -> None:
        tmp = tempfile.mkdtemp()
        lock_dir = os.path.join(tmp, "locks")
        os.makedirs(lock_dir, exist_ok=True)

        def child_try_acquire(queue: multiprocessing.Queue) -> None:
            from plate_core.leases.lease_adapters import LockfileLeaseAdapter
            from plate_core.leases.types import LeaseTags as LT

            inner = LockfileLeaseAdapter(Path(lock_dir), ttl_s=600)
            tgs = LT(
                repo="r",
                issue="1",
                state="ready",
                transition_id="t0",
                tier="T0",
                budget={},
            )
            # Distinct keys: idempotent replay must not mask cross-process exclusion.
            key = f"idem_mp_{os.getpid()}"
            r = inner.acquire(
                idempotency_key=key,
                requester="w",
                tags=tgs,
                claim_oid=None,
                wait_seconds=300,
            )
            queue.put((r.status, r.lease_id, r.wait_seconds))

        q: multiprocessing.Queue = multiprocessing.Queue()
        p1 = multiprocessing.Process(target=child_try_acquire, args=(q,))
        p2 = multiprocessing.Process(target=child_try_acquire, args=(q,))
        p1.start()
        p2.start()
        p1.join()
        p2.join()
        out = [q.get(timeout=30), q.get(timeout=30)]
        statuses = sorted(row[0] for row in out)
        self.assertEqual(statuses, ["granted", "wait"])
        granted = [row for row in out if row[0] == "granted"]
        waiting = [row for row in out if row[0] == "wait"]
        self.assertTrue(granted[0][1])
        self.assertEqual(waiting[0][2], 300)


class TestLeaseProcessConfig(unittest.TestCase):
    def test_process_yml_merges_defaults(self) -> None:
        root = Path(__file__).resolve().parents[1]
        merged = load_merged_process_config(root / ".agentic" / "process.yml")
        leases = merged["leases"]
        self.assertEqual(leases["adapter"], "local")
        self.assertEqual(leases["ttl_s"], 600)
        self.assertEqual(leases["grace_s"], 60)
        self.assertEqual(leases["no_capacity_deadline"], "6h")
        self.assertEqual(leases["no_capacity_deadline_s"], 6 * 3600)
        self.assertEqual(leases["revocations_before_human"], 3)

    def test_merge_inserts_defaults_when_leases_absent(self) -> None:
        merged = merge_process_config_with_defaults({"process": {"name": "x"}})
        self.assertEqual(merged["leases"]["ttl_s"], DEFAULT_LEASES_CONFIG["ttl_s"])

    def test_normalize_rejects_bad_adapter(self) -> None:
        with self.assertRaises(ValueError):
            normalize_leases_config({"adapter": ""})

    def test_factory_from_config(self) -> None:
        cfg = normalize_leases_config({})
        local_ad = lease_adapter_from_config(cfg)
        self.assertIsInstance(local_ad, LocalLeaseAdapter)


class TestMaxRunover(unittest.TestCase):
    def test_default_contract_max_overrun(self) -> None:
        ttl = DEFAULT_LEASES_CONFIG["ttl_s"]
        grace = DEFAULT_LEASES_CONFIG["grace_s"]
        self.assertEqual(max_lease_runover_seconds(ttl, grace), ttl // 3 + grace)

