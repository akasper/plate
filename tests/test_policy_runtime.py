"""Tests for policy runtime manifest and import verification (#1449)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from plate_core.policy_runtime import (
    describe_trust_prerequisite,
    load_manifest,
    verify_modules_importable,
)


class PolicyRuntimeTests(unittest.TestCase):
    def test_load_repo_manifest(self):
        root = Path(__file__).resolve().parents[1]
        manifest = load_manifest(root / ".agentic" / "policy-runtime.json")
        self.assertGreaterEqual(manifest.schema, 1)
        self.assertIn("plate_core.issue_context", manifest.required_modules)

    def test_current_src_passes_verify(self):
        errors = verify_modules_importable()
        self.assertEqual(errors, [], msg="; ".join(errors))

    def test_published_wheel_insufficient_modules(self):
        """PyPI plate-core 0.9.0 cannot satisfy the integration gate manifest alone."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".agentic").mkdir()
            (root / ".agentic" / "policy-runtime.json").write_text(
                json.dumps(
                    {
                        "schema": 1,
                        "plate_core_wheel": {
                            "max_known_published_version": "0.9.0",
                            "required_modules": [
                                "plate_core.issue_context",
                                "plate_core.pr_integration_base_gate",
                            ],
                        },
                    }
                ),
                encoding="utf-8",
            )
            manifest = load_manifest(root / ".agentic" / "policy-runtime.json")
            errors = verify_modules_importable(
                ["plate_core.definitely_not_in_09_wheel_for_test"]
            )
            self.assertTrue(errors)
            self.assertIn("definitely_not_in_09_wheel", errors[0])
            self.assertEqual(manifest.plate_core_max_known_wheel, "0.9.0")

    def test_trust_prerequisite_documents_limitation(self):
        text = describe_trust_prerequisite()
        self.assertIn("default-branch", text.lower())
        self.assertIn("malicious", text.lower())


if __name__ == "__main__":
    unittest.main()
