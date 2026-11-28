"""Helpers for sandboxing tests away from the real checkout (#1542)."""

from __future__ import annotations

import os
import tempfile
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def isolated_cwd():
    """Use a temp directory as cwd so default `.agentic/*` paths stay off the repo."""
    with tempfile.TemporaryDirectory() as tmp:
        orig = os.getcwd()
        try:
            os.chdir(tmp)
            yield Path(tmp)
        finally:
            os.chdir(orig)