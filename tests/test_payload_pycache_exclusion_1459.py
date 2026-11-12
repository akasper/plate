"""Regression: payload copy must omit __pycache__ and *.pyc (#1459)."""

import tempfile
import unittest
from pathlib import Path

from plate_core.import_payload import list_payload_relative_paths
from plate_core.template_payload import load_template_payload_manifest, should_include_template_file


class PayloadPycacheExclusionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = load_template_payload_manifest()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def test_installed_package_like_tree_omits_bytecode(self) -> None:
        """Simulate editable/install tree where scripts/plate/*.py was compiled."""
        plate = self.root / "scripts" / "plate"
        pycache = plate / "__pycache__"
        pycache.mkdir(parents=True)
        (plate / "foo.py").write_text("# stub\n", encoding="utf-8")
        (pycache / "foo.cpython-312.pyc").write_bytes(b"\x00\x00")

        rel_pyc = "scripts/plate/__pycache__/foo.cpython-312.pyc"
        rel_py = "scripts/plate/foo.py"

        self.assertFalse(should_include_template_file(rel_pyc, self.manifest))
        self.assertTrue(should_include_template_file(rel_py, self.manifest))

        listed = list_payload_relative_paths(self.root)
        self.assertIn(rel_py, listed)
        self.assertNotIn(rel_pyc, listed)
        self.assertEqual([p for p in listed if "pycache" in p or p.endswith(".pyc")], [])


if __name__ == "__main__":
    unittest.main()
