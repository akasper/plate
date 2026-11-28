"""#1193: mandatory adoption messaging content and next-steps contracts."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


class AdoptionMandatoryMessagingTests(unittest.TestCase):
    def test_monorepo_readme_declares_required_adoption_path(self):
        text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        for phrase in (
            "Adopting PLATE",
            "import-payload",
            "--adopt --apply",
            "adoption_complete",
        ):
            self.assertIn(phrase, text, msg=f"missing README phrase: {phrase}")

    def test_payload_agents_forbids_skipping_bootstrap(self):
        text = (
            REPO_ROOT / "src/plate_core/template_payload/AGENTS.md"
        ).read_text(encoding="utf-8")
        lowered = text.lower()
        self.assertIn("adoption_complete", text)
        self.assertIn("not optional", lowered)
        self.assertIn("import-payload", text)
        self.assertIn("bootstrap", text)

    def test_import_payload_next_steps_include_required_bootstrap_wording(self):
        from plate_core.import_payload import import_payload

        with tempfile.TemporaryDirectory() as tmp:
            report = import_payload(tmp, strategy="safe", apply=True)
            joined = "\n".join(report["next_steps"])
            self.assertIn("Required", joined)
            self.assertIn("bootstrap", report["next_command"])
            self.assertIn("adoption_complete", joined)


if __name__ == "__main__":
    unittest.main()