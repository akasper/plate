"""Public-surface compat contract tests (#1058).

Checked-in snapshot: ``tests/fixtures/public_surface_stable.json`` (stable CLI
invocations and flags, stable MCP tool input schemas, stable label names).

Deprecation registry: ``tests/fixtures/public_surface_deprecations.json`` — a
JSON **list** of objects::

    {
        "kind": "<kind>",
        "name": "<identifier>",
        "since": "<semver or date>",
        "replacement": "<optional successor id>"
    }

``kind`` is one of:

- ``cli_invocation`` — argparse path (e.g. ``"pr babysit"``)
- ``cli_flag`` — ``"<invocation>:<flag>"`` (e.g. ``"health:--json"``)
- ``mcp_tool`` — MCP tool name
- ``mcp_property`` — ``"<tool>:<property>"`` removed from input schema
- ``mcp_required_field`` — ``"<tool>:<field>"`` newly required (breaking)
- ``label`` — label name from ``.github/labels.yml``

When a stable item is removed, renamed, or a new required MCP field appears,
the contract test fails unless a matching deprecation entry exists. Additions to
the live surface do not fail the test.

Regenerate the snapshot::

    PYTHONPATH=src python3 scripts/regenerate_public_surface_stable.py

Verify the fixture is current::

    PYTHONPATH=src python3 scripts/regenerate_public_surface_stable.py --check
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from public_surface_contract_lib import (  # noqa: E402
    compare_stable_surface,
    load_deprecations,
    load_live_cli,
    load_live_labels,
    load_live_mcp_tools,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_PATH = REPO_ROOT / "tests" / "fixtures" / "public_surface_stable.json"
DEPRECATIONS_PATH = REPO_ROOT / "tests" / "fixtures" / "public_surface_deprecations.json"


class PublicSurfaceContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
        cls.deprecations = load_deprecations(DEPRECATIONS_PATH)

    def test_stable_surface_contract_matches_live_code(self) -> None:
        errors = compare_stable_surface(self.snapshot, deprecations=self.deprecations)
        self.assertEqual([], errors, msg="; ".join(errors))

    def test_additions_to_live_surface_do_not_fail_contract(self) -> None:
        live_cli = load_live_cli(set(self.snapshot.get("cli") or {}))
        live_cli["__synthetic_new_command__"] = ["--help"]
        live_mcp = load_live_mcp_tools()
        live_mcp["plate_synthetic_new_tool"] = {"properties": ["repo"], "required": []}
        live_labels = load_live_labels() + ["Synthetic Label"]
        errors = compare_stable_surface(
            self.snapshot,
            deprecations=self.deprecations,
            live_cli=live_cli,
            live_mcp=live_mcp,
            live_labels=live_labels,
        )
        self.assertEqual([], errors)

    def test_removing_stable_item_fails_without_deprecation(self) -> None:
        live_cli = load_live_cli(set(self.snapshot.get("cli") or {}))
        removed_inv = next(iter(live_cli))
        del live_cli[removed_inv]
        errors = compare_stable_surface(self.snapshot, deprecations=[], live_cli=live_cli)
        self.assertTrue(any("CLI invocation" in e for e in errors))

    def test_deprecation_entry_exempts_removed_stable_item(self) -> None:
        live_cli = load_live_cli(set(self.snapshot.get("cli") or {}))
        removed_inv = next(iter(live_cli))
        del live_cli[removed_inv]
        deprecations = [
            {
                "kind": "cli_invocation",
                "name": removed_inv,
                "since": "0.13.0",
                "replacement": "adopt",
            }
        ]
        errors = compare_stable_surface(
            self.snapshot,
            deprecations=deprecations,
            live_cli=live_cli,
        )
        self.assertEqual([], errors)

    def test_unresolved_invocation_omitted_from_live_cli(self) -> None:
        missing = "zzzz nonexistent plate invocation"
        live_cli = load_live_cli({missing})
        self.assertNotIn(missing, live_cli)

    def test_unresolved_stable_invocation_fails_as_removed(self) -> None:
        missing = "zzzz nonexistent plate invocation"
        snapshot = {
            "schema_version": 1,
            "cli": {missing: ["--help"]},
            "mcp_tools": {},
            "labels": [],
        }
        live_cli = load_live_cli(set(snapshot["cli"]))
        errors = compare_stable_surface(snapshot, deprecations=[], live_cli=live_cli)
        self.assertTrue(
            any("CLI invocation" in e and missing in e for e in errors),
            msg=errors,
        )

    def test_cli_invocation_deprecation_exempts_unresolved_invocation(self) -> None:
        missing = "zzzz nonexistent plate invocation"
        snapshot = {
            "schema_version": 1,
            "cli": {missing: ["--help"]},
            "mcp_tools": {},
            "labels": [],
        }
        live_cli = load_live_cli(set(snapshot["cli"]))
        deprecations = [
            {
                "kind": "cli_invocation",
                "name": missing,
                "since": "0.13.0",
                "replacement": "adopt",
            }
        ]
        errors = compare_stable_surface(
            snapshot,
            deprecations=deprecations,
            live_cli=live_cli,
        )
        self.assertEqual([], errors)


if __name__ == "__main__":
    unittest.main()