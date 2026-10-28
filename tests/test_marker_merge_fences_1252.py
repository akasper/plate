"""Regression tests for #1252: marker merge must ignore fenced example markers."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from plate_core.markers import (
    merge_with_diagnostics,
    validate_marker_document,
)
from plate_core.self_migrate import plan_marker_merge

_REPO_ROOT = Path(__file__).resolve().parents[1]

_UPSTREAM_TEMPLATE_SYNC_LOCAL = """<!-- PLATES-CORE:BEGIN upstream-template-sync -->
Local paragraph one.

Marker format:

```md
<!-- PLATES-CORE:BEGIN block-id -->
... content ...
<!-- PLATES-CORE:END block-id -->
```

Local footer in block.
<!-- PLATES-CORE:END upstream-template-sync -->
"""

_UPSTREAM_TEMPLATE_SYNC_UPSTREAM = """<!-- PLATES-CORE:BEGIN upstream-template-sync -->
Upstream paragraph one.
Upstream paragraph two NEW.

Marker format:

```md
<!-- PLATES-CORE:BEGIN block-id -->
... content ...
<!-- PLATES-CORE:END block-id -->
```

When introducing new guidance, wrap blocks.
<!-- PLATES-CORE:END upstream-template-sync -->
"""


class MarkerMergeFenceTests1252(unittest.TestCase):
    def test_merge_does_not_treat_fenced_example_end_as_section_close(self):
        """Example BEGIN/END inside a code fence must not truncate the real block."""
        result = merge_with_diagnostics(
            _UPSTREAM_TEMPLATE_SYNC_LOCAL,
            _UPSTREAM_TEMPLATE_SYNC_LOCAL,
            _UPSTREAM_TEMPLATE_SYNC_UPSTREAM,
        )
        text = result.text
        self.assertIn("Upstream paragraph two NEW.", text)
        self.assertEqual(text.count("Upstream paragraph one."), 1)
        self.assertEqual(text.count("Upstream paragraph two NEW."), 1)
        self.assertEqual(text.count("<!-- PLATES-CORE:END block-id -->"), 1)
        self.assertEqual(text.count("<!-- PLATES-CORE:END upstream-template-sync -->"), 1)
        self.assertEqual(text.count("```"), 2)
        # Corruption placed END block-id after the fence, before a stray footer/extra fence.
        self.assertNotIn(
            "<!-- PLATES-CORE:END block-id -->\n```\n\nLocal footer in block.",
            text,
        )
        validation = validate_marker_document(text)
        self.assertTrue(validation["valid"], validation.get("errors"))

    def test_plan_marker_merge_apply_writes_valid_upstream_template_sync(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            agents = root / "AGENTS.md"
            agents.write_text(_UPSTREAM_TEMPLATE_SYNC_LOCAL, encoding="utf-8")
            report = plan_marker_merge(
                root,
                paths=["AGENTS.md"],
                upstream_texts={"AGENTS.md": _UPSTREAM_TEMPLATE_SYNC_UPSTREAM},
                apply=True,
            )
            text = agents.read_text(encoding="utf-8")
        self.assertTrue(report["ok"], report.get("errors"))
        self.assertEqual(report["written"], 1)
        self.assertIn("Upstream paragraph two NEW.", text)
        validation = validate_marker_document(text)
        self.assertTrue(validation["valid"], validation.get("errors"))

    def test_inline_backtick_line_not_unclosed_fence_in_validation(self):
        """Pseudo-fence lines with backticks in info are not fences (#1253 review)."""
        doc = """<!-- PLATES-CORE:BEGIN demo -->
Document `` `literal` `` inline spans and pseudo-fences:

``` `literal` ```
```literal```

Real fence:

```md
<!-- PLATES-CORE:BEGIN block-id -->
x
<!-- PLATES-CORE:END block-id -->
```
<!-- PLATES-CORE:END demo -->
"""
        validation = validate_marker_document(doc)
        self.assertTrue(validation["valid"], validation.get("errors"))
        result = merge_with_diagnostics(doc, doc, doc.replace("x", "y"))
        self.assertTrue(validate_marker_document(result.text)["valid"])

    def test_validate_marker_document_rejects_corrupted_merge_shape(self):
        corrupted = """<!-- PLATES-CORE:BEGIN upstream-template-sync -->
Upstream paragraph one.

```md
<!-- PLATES-CORE:BEGIN block-id -->
... content ...
<!-- PLATES-CORE:END block-id -->
```
<!-- PLATES-CORE:END block-id -->
```
Local footer in block.
<!-- PLATES-CORE:END upstream-template-sync -->
"""
        validation = validate_marker_document(corrupted)
        self.assertFalse(validation["valid"])
        self.assertTrue(validation.get("errors"))

    def test_repo_agents_and_template_payload_pass_balance_check(self):
        for rel in (
            "AGENTS.md",
            "src/plate_core/template_payload/AGENTS.md",
        ):
            path = _REPO_ROOT / rel
            with path.open(encoding="utf-8") as fh:
                content = fh.read()
            validation = validate_marker_document(content)
            self.assertTrue(
                validation["valid"],
                f"{rel} failed marker/fence balance: {validation.get('errors')}",
            )


if __name__ == "__main__":
    unittest.main()
