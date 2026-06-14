"""plate_core runtime package."""

__version__ = "0.6.0"

# Core subsystems
from . import markers  # PLATES-CORE marker parsing, validation, and safe upstream sync (Issue #130)
from . import inventory  # Canonical methodology asset inventory (support for migration #131, health, etc.)

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
