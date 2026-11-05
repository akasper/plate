"""Atomic, locked JSON persistence and explicit transition helper (#1368)."""

from __future__ import annotations

import json
import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator, Sequence

from .pr_watch_guards import atomic_write_json

__all__ = [
    "Machine",
    "IllegalTransition",
    "CorruptStateError",
    "locked_json",
    "atomic_write_json",
    "load_strict",
    "assert_terminal_states_have_no_outgoing",
    "save_refused",
    "clear_save_refusal",
]

Transition = tuple[str, str, str]

# Empty lockfiles from a crashed creator between O_EXCL and pid write are not stale
# until older than this grace window.
_EMPTY_LOCK_MAX_AGE_SEC = 5.0

_refuse_save: set[str] = set()


class IllegalTransition(Exception):
    """Raised when a state machine rejects a (state, event) pair."""


class CorruptStateError(Exception):
    """Raised when on-disk JSON is torn or truncated, or save is refused after corruption."""


class Machine:
    """Small explicit transition table for record status fields."""

    def __init__(
        self,
        name: str,
        states: Sequence[str],
        initial: str,
        terminal: Sequence[str],
        table: Sequence[Transition],
    ) -> None:
        self.name = name
        self.states = set(states)
        self.initial = initial
        self.terminal = set(terminal)
        self.table = {(f, e): t for f, e, t in table}

    def next(self, current: str, event: str) -> str:
        if current not in self.states:
            raise IllegalTransition(f"{self.name}: unknown state {current!r}")
        try:
            return self.table[(current, event)]
        except KeyError as exc:
            raise IllegalTransition(
                f"{self.name}: {event!r} not allowed from {current!r}"
            ) from exc


def assert_terminal_states_have_no_outgoing(machine: Machine) -> None:
    """Sanity-check that no transition leaves a terminal state."""
    for (from_state, _event), _to_state in machine.table.items():
        if from_state in machine.terminal:
            raise ValueError(
                f"{machine.name}: terminal state {from_state!r} has outgoing transition"
            )


def _path_key(path: Path) -> str:
    return str(path.resolve())


def save_refused(path: Path | str) -> bool:
    return _path_key(Path(path)) in _refuse_save


def clear_save_refusal(path: Path | str) -> None:
    _refuse_save.discard(_path_key(Path(path)))


def _mark_corrupt(path: Path) -> None:
    _refuse_save.add(_path_key(path))


def _pid_is_alive(pid: int) -> bool:
    try:
        pid_i = int(pid)
    except (TypeError, ValueError):
        return False
    if pid_i <= 0:
        return False
    if sys.platform == "win32":
        import ctypes

        kernel = ctypes.windll.kernel32
        handle = kernel.OpenProcess(0x1000, False, pid_i)
        if handle:
            kernel.CloseHandle(handle)
            return True
        return kernel.GetLastError() != 5
    try:
        os.kill(pid_i, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    else:
        return True


def _lockfile_age_sec(lock_path: Path, stat: os.stat_result) -> float:
    return max(0.0, time.time() - stat.st_mtime)


def _lock_is_stale(lock_path: Path) -> bool:
    try:
        stat = lock_path.stat()
    except FileNotFoundError:
        return False
    except OSError:
        return False

    try:
        raw = lock_path.read_text(encoding="utf-8").strip()
        if not raw:
            return _lockfile_age_sec(lock_path, stat) > _EMPTY_LOCK_MAX_AGE_SEC
        pid = int(raw.split()[0])
    except (OSError, ValueError, IndexError):
        return _lockfile_age_sec(lock_path, stat) > _EMPTY_LOCK_MAX_AGE_SEC
    return not _pid_is_alive(pid)


@contextmanager
def _lockfile(lock_path: Path) -> Iterator[None]:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    acquired = False
    fd: int | None = None
    while not acquired:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            acquired = True
        except FileExistsError:
            if _lock_is_stale(lock_path):
                try:
                    lock_path.unlink()
                except OSError:
                    pass
                continue
            time.sleep(0.02)
    try:
        assert fd is not None
        os.write(fd, f"{os.getpid()}\n".encode("ascii"))
        os.close(fd)
        fd = None
        yield
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        try:
            lock_path.unlink()
        except OSError:
            pass


def load_strict(path: Path | str) -> Any:
    """Load JSON from ``path``; torn or empty content raises ``CorruptStateError``."""
    target = Path(path)
    try:
        text = target.read_text(encoding="utf-8")
    except OSError as exc:
        raise CorruptStateError(f"cannot read state at {target}") from exc
    stripped = text.strip()
    if not stripped:
        _mark_corrupt(target)
        raise CorruptStateError(f"empty or torn JSON at {target}")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        _mark_corrupt(target)
        raise CorruptStateError(f"corrupt JSON at {target}: {exc}") from exc


@contextmanager
def locked_json(
    path: Path | str,
    *,
    missing_factory: Callable[[], dict[str, Any]] | None = None,
) -> Iterator[dict[str, Any]]:
    """Load (or create) a JSON object under an exclusive lock, then atomically persist."""
    target = Path(path)
    lock_path = target.with_suffix(target.suffix + ".lock")

    if save_refused(target):
        raise CorruptStateError(f"refusing locked access to corrupt store {target}")

    with _lockfile(lock_path):
        if save_refused(target):
            raise CorruptStateError(f"refusing locked access to corrupt store {target}")

        if target.exists():
            payload = load_strict(target)
            if not isinstance(payload, dict):
                _mark_corrupt(target)
                raise CorruptStateError(f"expected JSON object at {target}")
            data: dict[str, Any] = payload
        else:
            data = missing_factory() if missing_factory is not None else {}
            if not isinstance(data, dict):
                raise TypeError("missing_factory must return a dict")

        yield data

        if save_refused(target):
            raise CorruptStateError(f"refusing save for corrupt store {target}")

        atomic_write_json(target, data)
        clear_save_refusal(target)
