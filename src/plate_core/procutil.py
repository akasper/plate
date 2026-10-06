"""Subprocess helper that does not flash a console on Windows (#1073).

``gh``, ``git``, and ``cmd.exe`` are console-subsystem programs. When a
windowless parent starts them without ``CREATE_NO_WINDOW``, each child
allocates a console, steals focus, and tears it down. One helper owns the
Windows flags, UTF-8 text mode, and the quiet ``gh`` environment.
"""

from __future__ import annotations

import os
import subprocess
import sys
from typing import Any, Mapping

# Process-creation flag: do not allocate a console for the child.
CREATE_NO_WINDOW = 0x08000000
STARTF_USESHOWWINDOW = 0x00000001
SW_HIDE = 0

# gh itself spawns ``tzutil`` for telemetry and an update check. Both flash
# another console on Windows. These defaults are applied only when the caller
# did not set them.
_QUIET_ENV_DEFAULTS = {
    "GH_NO_UPDATE_NOTIFIER": "1",
    "DO_NOT_TRACK": "1",
}


def hidden_subprocess_kwargs(kwargs: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Copy ``kwargs`` and add Windows console-hiding plus UTF-8 text defaults.

    Rejects ``shell=True``. A shell would insert ``cmd.exe /c`` and flash a
    window before the real program starts. Does not mutate the caller's mapping.
    """
    out = dict(kwargs or {})
    if out.get("shell"):
        raise ValueError("hidden subprocess helper does not accept shell=True")
    if out.get("text") or out.get("universal_newlines"):
        out.setdefault("encoding", "utf-8")
        out.setdefault("errors", "replace")
    env_in = out.get("env")
    env = dict(os.environ if env_in is None else env_in)
    for key, value in _QUIET_ENV_DEFAULTS.items():
        env.setdefault(key, value)
    out["env"] = env
    if sys.platform == "win32":
        out["creationflags"] = int(out.get("creationflags") or 0) | CREATE_NO_WINDOW
        # STARTUPINFO exists on Windows CPython. Guarded so a test can force
        # win32 on other platforms and still assert creationflags.
        startupinfo_cls = getattr(subprocess, "STARTUPINFO", None)
        if startupinfo_cls is not None:
            startup = out.get("startupinfo")
            if startup is None:
                startup = startupinfo_cls()
            startup.dwFlags |= STARTF_USESHOWWINDOW
            startup.wShowWindow = SW_HIDE
            out["startupinfo"] = startup
    return out


def run_hidden(
    args: list[str] | tuple[str, ...],
    **kwargs: Any,
) -> subprocess.CompletedProcess[Any]:
    """``subprocess.run`` with no visible console on Windows."""
    return subprocess.run(args, **hidden_subprocess_kwargs(kwargs))


def check_call_hidden(args: list[str] | tuple[str, ...], **kwargs: Any) -> int:
    """``subprocess.check_call`` with no visible console on Windows."""
    return subprocess.check_call(args, **hidden_subprocess_kwargs(kwargs))


def check_output_hidden(args: list[str] | tuple[str, ...], **kwargs: Any) -> Any:
    """``subprocess.check_output`` with no visible console on Windows."""
    return subprocess.check_output(args, **hidden_subprocess_kwargs(kwargs))
