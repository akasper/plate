"""Regression tests for #1499: cut_release in adopter repos.

Adopter repositories have no ``pyproject.toml`` and no ``src/plate_core``
package. Historically ``cut_release`` and ``validate_release_workspace``
called :func:`plate_core.version_sync.find_repo_root`, which raised
``RuntimeError: Could not locate repository root`` for those layouts.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

# Make the scripts/ directory importable for the script-level regression test.
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from plate_core import release as core_release  # noqa: E402

import cut_release as script_cut_release  # noqa: E402


def _make_adopter_repo(tmp: str) -> Path:
    """Create an adopter layout: fragments under .agentic/releases only.

    Deliberately omits pyproject.toml and src/plate_core to reproduce #1499.
    """
    root = Path(tmp)
    unreleased = root / ".agentic" / "releases" / "unreleased"
    unreleased.mkdir(parents=True)
    fragment = {
        "slug": "adopter-change",
        "change_type": "feature",
        "surface": "docs/",
        "summary": "Adopter feature fragment.",
        "migration_impact": "None.",
        "agent_notes": "Run the targeted tests.",
        "links": ["#1499"],
    }
    (unreleased / "adopter-change.json").write_text(json.dumps(fragment), encoding="utf-8")
    return root


class CutReleaseAdopterDryRunTests(unittest.TestCase):
    def test_core_cut_release_dry_run_succeeds_and_writes_nothing(self):
        with TemporaryDirectory() as tmp:
            root = _make_adopter_repo(tmp)
            releases = root / ".agentic" / "releases"

            rc = core_release.cut_release(version="v1.0.0", releases_dir=releases, dry_run=True)

            self.assertEqual(rc, 0)
            self.assertFalse((releases / "v1.0.0").exists())
            self.assertTrue((releases / "unreleased" / "adopter-change.json").exists())


class CutReleaseAdopterTests(unittest.TestCase):
    def test_core_cut_release_writes_release_and_moves_fragments(self):
        with TemporaryDirectory() as tmp:
            root = _make_adopter_repo(tmp)
            releases = root / ".agentic" / "releases"

            rc = core_release.cut_release(version="v1.0.0", releases_dir=releases)

            self.assertEqual(rc, 0)
            release_file = releases / "v1.0.0" / "release.json"
            self.assertTrue(release_file.exists())
            data = json.loads(release_file.read_text(encoding="utf-8"))
            self.assertEqual(data["version"], "1.0.0")
            moved = releases / "v1.0.0" / "fragments" / "adopter-change.json"
            self.assertTrue(moved.exists())
            self.assertFalse((releases / "unreleased" / "adopter-change.json").exists())
            # No plate-core version surfaces were created in the adopter tree.
            self.assertFalse((root / "pyproject.toml").exists())
            self.assertFalse((root / "src" / "plate_core" / "__init__.py").exists())


class ValidateReleaseWorkspaceAdopterTests(unittest.TestCase):
    def test_validate_release_workspace_does_not_raise_for_adopter(self):
        with TemporaryDirectory() as tmp:
            root = _make_adopter_repo(tmp)

            report = core_release.validate_release_workspace(root)

            self.assertIsNone(report.release_version)
            self.assertIsNone(report.release_tag)
            self.assertEqual(report.version_files, {})
            self.assertEqual(report.errors, [])


class ScriptCutReleaseAdopterTests(unittest.TestCase):
    def test_script_cut_release_works_in_adopter(self):
        with TemporaryDirectory() as tmp:
            root = _make_adopter_repo(tmp)
            releases = root / ".agentic" / "releases"

            rc = script_cut_release.cut_release(version="v1.0.0", releases_dir=releases)

            self.assertEqual(rc, 0)
            release_file = releases / "v1.0.0" / "release.json"
            self.assertTrue(release_file.exists())
            data = json.loads(release_file.read_text(encoding="utf-8"))
            self.assertEqual(data["version"], "1.0.0")
            self.assertTrue((releases / "v1.0.0" / "fragments" / "adopter-change.json").exists())
            self.assertFalse((releases / "unreleased" / "adopter-change.json").exists())


class AdopterWithOnlyPyprojectTests(unittest.TestCase):
    """An adopter with an unrelated pyproject.toml must not be version-synced."""

    def test_cut_release_with_only_pyproject_succeeds_and_leaves_it_untouched(self):
        with TemporaryDirectory() as tmp:
            root = _make_adopter_repo(tmp)
            pyproject = root / "pyproject.toml"
            pyproject.write_text('[project]\nname = "app"\nversion = "0.0.1"\n', encoding="utf-8")
            releases = root / ".agentic" / "releases"

            rc = core_release.cut_release(version="v1.0.0", releases_dir=releases)

            self.assertEqual(rc, 0)
            self.assertTrue((releases / "v1.0.0" / "release.json").exists())
            self.assertIn('version = "0.0.1"', pyproject.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
