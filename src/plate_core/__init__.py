"""plate_core runtime package."""

# Core subsystems
from . import markers  # PLATES-CORE marker parsing, validation, and safe upstream sync (Issue #130)

# Public marker API (for CLI, MCP, template sync, and extensions)
from .markers import (
    MarkerParser,
    MarkerParseError,
    MarkerSection,
)

__all__ = [
    "markers",
    "MarkerParser",
    "MarkerParseError",
    "MarkerSection",
]
