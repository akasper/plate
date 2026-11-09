"""Tests for local issue lifecycle JSONL log (#1422)."""

from __future__ import annotations

import json
import multiprocessing
import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from plate_core.issue_lifecycle_events import (
    append_issue_lifecycle_event,
    iterate_issue_lifecycle_events,
    mint_ulid,
    scrub_issue_lifecycle_payload,
)


def _mp_child_writer_id(root_str: str, out: multiprocessing.Queue) -> None:
    from pathlib import Path

    from plate_core.issue_lifecycle_events import _get_or_create_writer_id

    out.put(_get_or_create_writer_id(Path(root_str)))


class IssueLifecycleEventLogTests(unittest.TestCase):
    def test_seq_monotonic_per_writer_across_restarts(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = "o/r"
            append_issue_lifecycle_event(
                repo,
                1,
                event_type="error",
                summary="a",
                plate_root=root,
            )
            seq_path = root / ".agentic" / "events" / "o-r"
            writer_dirs = [p for p in seq_path.iterdir() if p.is_dir()]
            self.assertEqual(len(writer_dirs), 1)
            wid = writer_dirs[0].name
            seq1 = json.loads((seq_path / wid / "seq.json").read_text(encoding="utf-8"))[
                "next_seq"
            ]

            append_issue_lifecycle_event(
                repo,
                2,
                event_type="retry",
                summary="b",
                plate_root=root,
            )
            seq2 = json.loads((seq_path / wid / "seq.json").read_text(encoding="utf-8"))[
                "next_seq"
            ]
            self.assertEqual(seq2, seq1 + 1)

            # Simulated restart: recreate the module entrypoint but same on-disk writer_id.
            with mock.patch(
                "plate_core.issue_lifecycle_events._mint_writer_id",
                side_effect=AssertionError("writer_id must be read from disk, not reminted"),
            ):
                append_issue_lifecycle_event(
                    repo,
                    1,
                    event_type="abandon",
                    summary="c",
                    plate_root=root,
                )
            seq3 = json.loads((seq_path / wid / "seq.json").read_text(encoding="utf-8"))[
                "next_seq"
            ]
            self.assertEqual(seq3, seq2 + 1)

    def test_event_key_stable_on_retry(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            tid = "retry-suite"
            r1 = append_issue_lifecycle_event(
                "a/b",
                9,
                event_type="state_transition",
                transition_id=tid,
                summary="first",
                plate_root=root,
            )
            r2 = append_issue_lifecycle_event(
                "a/b",
                9,
                event_type="state_transition",
                transition_id=tid,
                summary="second try",
                plate_root=root,
            )
            self.assertEqual(r1["event_key"], f"{tid}:state_transition")
            self.assertEqual(r2["event_key"], r1["event_key"])
            self.assertNotEqual(r1["event_id"], r2["event_id"])

    def test_transition_event_key_from_transition_id(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            tid = "tr-42"
            row = append_issue_lifecycle_event(
                "org/repo",
                100,
                event_type="pm_decision",
                transition_id=tid,
                summary="decision",
                plate_root=root,
            )
            self.assertEqual(row["event_key"], "tr-42:pm_decision")

    def test_scrubber_redacts_token_patterns_before_append(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            secret = "ghp_" + "a" * 36
            append_issue_lifecycle_event(
                "x/y",
                3,
                event_type="error",
                summary=f"failed auth {secret}",
                plate_root=root,
            )
            log = root / ".agentic" / "events" / "x-y" / "issue-3.jsonl"
            line = log.read_text(encoding="utf-8").strip()
            self.assertIn("[REDACTED_TOKEN]", line)
            self.assertNotIn(secret, line)

        scrubbed = scrub_issue_lifecycle_payload({"t": "Bearer sometokenvaluehere"})
        self.assertEqual(scrubbed["t"], "Bearer [REDACTED_TOKEN]")

    def test_event_key_scrubs_transition_id_tokens(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            secret = "ghp_" + "x" * 36
            tid = f" lbl:{secret}:end "
            row = append_issue_lifecycle_event(
                "a/b",
                1,
                event_type="state_transition",
                transition_id=tid,
                summary="ok",
                plate_root=root,
            )
            # Strip + scrub must run before event_key is formed.
            self.assertEqual(
                row["event_key"],
                f"lbl:[REDACTED_TOKEN]:end:state_transition",
            )
            log_line = (
                root / ".agentic" / "events" / "a-b" / "issue-1.jsonl"
            ).read_text(encoding="utf-8")
            self.assertNotIn(secret, log_line)

    def test_writer_id_file_cross_process_single_id(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            ctx = multiprocessing.get_context("spawn")
            q: multiprocessing.Queue = ctx.Queue()
            proc = ctx.Process(target=_mp_child_writer_id, args=(str(tmp), q))
            proc.start()
            from_child = q.get(timeout=30)
            proc.join(timeout=30)
            self.assertEqual(proc.exitcode, 0)

            from plate_core.issue_lifecycle_events import _get_or_create_writer_id

            from_parent = _get_or_create_writer_id(root)

            self.assertEqual(from_parent, from_child)
            path = root / ".agentic" / "events" / "writer_id"
            self.assertTrue(path.is_file())
            self.assertEqual(path.read_text(encoding="utf-8").strip(), from_parent)

    def test_writer_id_recover_empty_file(self):
        """Crash after O_EXCL create but before write leaves empty writer_id; recover."""
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            wid_path = root / ".agentic" / "events" / "writer_id"
            wid_path.parent.mkdir(parents=True, exist_ok=True)
            wid_path.write_text("", encoding="utf-8")

            row = append_issue_lifecycle_event(
                "a/b",
                1,
                event_type="error",
                summary="after recovery",
                plate_root=root,
            )
            line = wid_path.read_text(encoding="utf-8").strip()
            self.assertEqual(len(line), 26)
            self.assertTrue(line.isalnum())
            self.assertEqual(row["writer_id"], line)

    def test_writer_id_recover_truncated_ulid(self):
        """Partial line from interrupted write is not a valid id; replace under lock."""
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            wid_path = root / ".agentic" / "events" / "writer_id"
            wid_path.parent.mkdir(parents=True, exist_ok=True)
            wid_path.write_text(mint_ulid()[:10], encoding="utf-8")

            row = append_issue_lifecycle_event(
                "a/b",
                1,
                event_type="retry",
                summary="ok",
                plate_root=root,
            )
            line = wid_path.read_text(encoding="utf-8").strip()
            self.assertEqual(len(line), 26)
            self.assertEqual(row["writer_id"], line)

    def test_concurrent_append_no_torn_lines(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = "c/d"
            n_threads = 12
            per_thread = 40
            errors: list[BaseException] = []

            def worker(tid: int) -> None:
                try:
                    for i in range(per_thread):
                        append_issue_lifecycle_event(
                            repo,
                            7,
                            event_type="ci_gate",
                            summary=f"t{tid}-i{i}",
                            plate_root=root,
                        )
                except BaseException as exc:
                    errors.append(exc)

            threads = [
                threading.Thread(target=worker, args=(t,)) for t in range(n_threads)
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            self.assertEqual(errors, [])

            log = root / ".agentic" / "events" / "c-d" / "issue-7.jsonl"
            for raw in log.read_text(encoding="utf-8").splitlines():
                if not raw.strip():
                    continue
                row = json.loads(raw)
                self.assertIn("event_id", row)
                self.assertIn("seq", row)

    def test_summary_truncated_to_500(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            big = "α" * 600
            row = append_issue_lifecycle_event(
                "o/r",
                1,
                event_type="error",
                summary=big,
                plate_root=root,
            )
            self.assertEqual(len(row["summary"]), 500)
            self.assertTrue(row["summary"].endswith("…"))


class IterateEventsTests(unittest.TestCase):
    def test_iterate_ordered(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            append_issue_lifecycle_event(
                "p/q", 5, event_type="pr_opened", summary="a", plate_root=root
            )
            append_issue_lifecycle_event(
                "p/q", 5, event_type="pr_merged", summary="b", plate_root=root
            )
            rows = list(iterate_issue_lifecycle_events("p/q", 5, plate_root=root))
            self.assertEqual([r["summary"] for r in rows], ["a", "b"])


class UlidTests(unittest.TestCase):
    def test_mint_ulid_length_and_order(self):
        a = mint_ulid(when_ms=1000)
        b = mint_ulid(when_ms=2000)
        self.assertEqual(len(a), 26)
        self.assertEqual(len(b), 26)
        self.assertLess(a, b)


if __name__ == "__main__":
    unittest.main()
