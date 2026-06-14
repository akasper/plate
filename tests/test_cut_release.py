"""Tests for scripts/cut_release.py — auto-version detection and epic-dir support."""

from __future__ import annotations

import contextlib
import json
import sys
import unittest
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

# Make the scripts/ directory importable
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from cut_release import (
    bump_version,
    build_release,
    collect_fragments,
    cut_release,
    detect_latest_version,
    fmt_version,
    infer_bump_type,
    parse_version,
)


def _seed_version_files(repo_root: Path, version: str = "0.1.4") -> None:
    (repo_root / "src" / "plate_core").mkdir(parents=True, exist_ok=True)
    (repo_root / "plugin").mkdir(parents=True, exist_ok=True)
    (repo_root / ".plugin").mkdir(parents=True, exist_ok=True)
    (repo_root / ".github" / "plugin").mkdir(parents=True, exist_ok=True)
    (repo_root / "src" / "plate_core" / "__init__.py").write_text(
        f'"""plate_core runtime package."""\n\n__version__ = "{version}"\n',
        encoding="utf-8",
    )
    (repo_root / "pyproject.toml").write_text(
        '\n'.join(
            [
                "[project]",
                'name = "plate-core"',
                f'version = "{version}"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    plugin_manifest = {
        "name": "plate-core",
        "version": version,
        "repository": "https://github.com/akasper/plate",
    }
    (repo_root / "plugin" / "plugin.json").write_text(json.dumps(plugin_manifest), encoding="utf-8")
    (repo_root / ".plugin" / "plugin.json").write_text(json.dumps(plugin_manifest), encoding="utf-8")
    (repo_root / ".github" / "plugin" / "marketplace.json").write_text(
        json.dumps(
            {
                "name": "plate-marketplace",
                "metadata": {"version": version},
                "plugins": [{"name": "plate-core", "source": "plugin", "version": version}],
            }
        ),
        encoding="utf-8",
    )


def _assert_version_files(repo_root: Path, version: str) -> None:
    runtime = (repo_root / "src" / "plate_core" / "__init__.py").read_text(encoding="utf-8")
    pyproject = (repo_root / "pyproject.toml").read_text(encoding="utf-8")
    plugin_manifest = json.loads((repo_root / "plugin" / "plugin.json").read_text(encoding="utf-8"))
    root_plugin_manifest = json.loads((repo_root / ".plugin" / "plugin.json").read_text(encoding="utf-8"))
    marketplace_manifest = json.loads((repo_root / ".github" / "plugin" / "marketplace.json").read_text(encoding="utf-8"))
    assert f'__version__ = "{version}"' in runtime
    assert f'version = "{version}"' in pyproject
    assert plugin_manifest["version"] == version
    assert root_plugin_manifest["version"] == version
    assert marketplace_manifest["metadata"]["version"] == version
    assert marketplace_manifest["plugins"][0]["version"] == version


# ---------------------------------------------------------------------------
# Version helpers
# ---------------------------------------------------------------------------


class ParseVersionTests(unittest.TestCase):
    def test_bare(self):
        self.assertEqual(parse_version("1.2.3"), (1, 2, 3))

    def test_v_prefix(self):
        self.assertEqual(parse_version("v0.1.4"), (0, 1, 4))

    def test_invalid(self):
        self.assertIsNone(parse_version("not-a-version"))

    def test_two_part(self):
        self.assertIsNone(parse_version("1.2"))


class BumpVersionTests(unittest.TestCase):
    def test_patch(self):
        self.assertEqual(bump_version((0, 1, 4), "patch"), (0, 1, 5))

    def test_minor(self):
        self.assertEqual(bump_version((0, 1, 4), "minor"), (0, 2, 0))

    def test_major(self):
        self.assertEqual(bump_version((0, 1, 4), "major"), (1, 0, 0))

    def test_minor_resets_patch(self):
        self.assertEqual(bump_version((1, 3, 7), "minor"), (1, 4, 0))

    def test_major_resets_minor_and_patch(self):
        self.assertEqual(bump_version((2, 5, 3), "major"), (3, 0, 0))


# ---------------------------------------------------------------------------
# Baseline detection
# ---------------------------------------------------------------------------


class DetectLatestVersionTests(unittest.TestCase):
    def test_flat_files(self):
        with TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "unreleased").mkdir()
            (d / "v0.1.0.json").write_text('{"version":"0.1.0"}')
            (d / "v0.1.3.json").write_text('{"version":"0.1.3"}')
            (d / "v0.1.1.json").write_text('{"version":"0.1.1"}')
            self.assertEqual(detect_latest_version(d), (0, 1, 3))

    def test_versioned_dirs(self):
        with TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "v0.2.0").mkdir()
            (d / "v0.2.0" / "release.json").write_text('{"version":"0.2.0"}')
            (d / "v0.1.9").mkdir()
            (d / "v0.1.9" / "release.json").write_text('{"version":"0.1.9"}')
            self.assertEqual(detect_latest_version(d), (0, 2, 0))

    def test_mixed_flat_and_dirs_picks_highest(self):
        with TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "v0.1.4.json").write_text('{"version":"0.1.4"}')
            (d / "v0.2.0").mkdir()
            (d / "v0.2.0" / "release.json").write_text('{"version":"0.2.0"}')
            self.assertEqual(detect_latest_version(d), (0, 2, 0))

    def test_no_releases_returns_none(self):
        with TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "unreleased").mkdir()
            self.assertIsNone(detect_latest_version(d))

    def test_dir_without_release_json_ignored(self):
        with TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "v0.3.0").mkdir()  # no release.json inside
            (d / "v0.1.0.json").write_text('{"version":"0.1.0"}')
            self.assertEqual(detect_latest_version(d), (0, 1, 0))


# ---------------------------------------------------------------------------
# Fragment collection
# ---------------------------------------------------------------------------


def _write_fragment(directory: Path, name: str, data: dict) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(json.dumps(data), encoding="utf-8")


class CollectFragmentsTests(unittest.TestCase):
    def test_unreleased_only(self):
        with TemporaryDirectory() as tmp:
            d = Path(tmp)
            _write_fragment(d / "unreleased", "a.json", {"slug": "a", "change_type": "feature"})
            _write_fragment(d / "unreleased", "b.json", {"slug": "b", "change_type": "docs"})
            frags = collect_fragments(d)
            self.assertEqual(len(frags), 2)
            slugs = [f["slug"] for f in frags]
            self.assertIn("a", slugs)
            self.assertIn("b", slugs)

    def test_epic_dir_only(self):
        with TemporaryDirectory() as tmp:
            d = Path(tmp)
            _write_fragment(d / "epic-42-cool-feature", "cool.json", {"slug": "cool", "change_type": "feature"})
            frags = collect_fragments(d)
            self.assertEqual(len(frags), 1)
            self.assertEqual(frags[0]["_source_label"], "epic-42-cool-feature")

    def test_mixed_sources(self):
        with TemporaryDirectory() as tmp:
            d = Path(tmp)
            _write_fragment(d / "unreleased", "x.json", {"slug": "x"})
            _write_fragment(d / "epic-10-foo", "y.json", {"slug": "y"})
            _write_fragment(d / "epic-11-bar", "z.json", {"slug": "z"})
            frags = collect_fragments(d)
            self.assertEqual(len(frags), 3)

    def test_no_sources_returns_empty(self):
        with TemporaryDirectory() as tmp:
            d = Path(tmp)
            self.assertEqual(collect_fragments(d), [])

    def test_source_label_set_for_unreleased(self):
        with TemporaryDirectory() as tmp:
            d = Path(tmp)
            _write_fragment(d / "unreleased", "f.json", {"slug": "f"})
            frags = collect_fragments(d)
            self.assertEqual(frags[0]["_source_label"], "unreleased")


# ---------------------------------------------------------------------------
# Bump type inference
# ---------------------------------------------------------------------------


class InferBumpTypeTests(unittest.TestCase):
    def test_breaking_triggers_major(self):
        frags = [{"change_type": "feature", "breaking": True}]
        self.assertEqual(infer_bump_type(frags), "major")

    def test_feature_triggers_minor(self):
        frags = [{"change_type": "feature"}, {"change_type": "docs"}]
        self.assertEqual(infer_bump_type(frags), "minor")

    def test_docs_only_triggers_patch(self):
        frags = [{"change_type": "docs"}, {"change_type": "process"}]
        self.assertEqual(infer_bump_type(frags), "patch")

    def test_mixed_feature_and_breaking_is_major(self):
        frags = [{"change_type": "feature"}, {"change_type": "fix", "breaking": True}]
        self.assertEqual(infer_bump_type(frags), "major")


# ---------------------------------------------------------------------------
# End-to-end cut_release()
# ---------------------------------------------------------------------------


class CutReleaseAutoVersionTests(unittest.TestCase):
    def _make_releases_dir(self, tmp: str) -> Path:
        d = Path(tmp)
        _seed_version_files(d)
        (d / "v0.1.4.json").write_text('{"version":"0.1.4"}')
        unreleased = d / "unreleased"
        unreleased.mkdir()
        _write_fragment(
            unreleased,
            "cool.json",
            {"slug": "cool", "change_type": "feature", "surface": "s", "migration_impact": "m", "agent_notes": "n"},
        )
        return d

    def test_auto_minor_bump_from_flat_baseline(self):
        with TemporaryDirectory() as tmp:
            d = self._make_releases_dir(tmp)
            rc = cut_release(version=None, releases_dir=d)
            self.assertEqual(rc, 0)
            self.assertTrue((d / "v0.2.0" / "release.json").exists())
            data = json.loads((d / "v0.2.0" / "release.json").read_text())
            self.assertEqual(data["version"], "0.2.0")
            _assert_version_files(d, "0.2.0")

    def test_cut_prints_release_pr_creation_guidance_with_both_labels(self):
        """Regression test for #532: cut_release next-steps must instruct to use BOTH
        Documentation + Release labels on the Release PR (for heavy CI + legacy support).
        The printed gh pr create example and "BOTH labels" / see #532 note anchor the fix.
        """
        with TemporaryDirectory() as tmp:
            d = self._make_releases_dir(tmp)
            buf = StringIO()
            with contextlib.redirect_stdout(buf):
                rc = cut_release(version=None, releases_dir=d)
            self.assertEqual(rc, 0)
            out = buf.getvalue()
            self.assertIn('--label "Documentation" --label "Release"', out)
            self.assertIn("Use BOTH labels so heavy CI runs (see #532)", out)

    def test_auto_patch_bump_when_only_docs(self):
        with TemporaryDirectory() as tmp:
            d = Path(tmp)
            _seed_version_files(d)
            (d / "v0.1.4.json").write_text('{"version":"0.1.4"}')
            _write_fragment(
                d / "unreleased",
                "doc.json",
                {"slug": "doc", "change_type": "docs", "surface": "s", "migration_impact": "m", "agent_notes": "n"},
            )
            rc = cut_release(version=None, releases_dir=d)
            self.assertEqual(rc, 0)
            self.assertTrue((d / "v0.1.5" / "release.json").exists())
            _assert_version_files(d, "0.1.5")

    def test_version_type_override(self):
        with TemporaryDirectory() as tmp:
            d = self._make_releases_dir(tmp)
            rc = cut_release(version=None, releases_dir=d, version_type="patch")
            self.assertEqual(rc, 0)
            self.assertTrue((d / "v0.1.5" / "release.json").exists())
            _assert_version_files(d, "0.1.5")

    def test_explicit_version_used(self):
        with TemporaryDirectory() as tmp:
            d = self._make_releases_dir(tmp)
            rc = cut_release(version="v1.0.0", releases_dir=d)
            self.assertEqual(rc, 0)
            self.assertTrue((d / "v1.0.0" / "release.json").exists())
            _assert_version_files(d, "1.0.0")

    def test_no_baseline_and_no_version_returns_error(self):
        with TemporaryDirectory() as tmp:
            d = Path(tmp)
            _seed_version_files(d)
            _write_fragment(
                d / "unreleased",
                "x.json",
                {"slug": "x", "change_type": "feature", "surface": "s", "migration_impact": "m", "agent_notes": "n"},
            )
            rc = cut_release(version=None, releases_dir=d)
            self.assertEqual(rc, 1)

    def test_no_fragments_returns_error(self):
        with TemporaryDirectory() as tmp:
            d = Path(tmp)
            _seed_version_files(d)
            (d / "v0.1.4.json").write_text('{"version":"0.1.4"}')
            rc = cut_release(version="v0.1.5", releases_dir=d)
            self.assertEqual(rc, 1)

    def test_fragments_moved_to_versioned_dir(self):
        with TemporaryDirectory() as tmp:
            d = self._make_releases_dir(tmp)
            cut_release(version=None, releases_dir=d)
            self.assertFalse((d / "unreleased" / "cool.json").exists())
            self.assertTrue((d / "v0.2.0" / "fragments" / "cool.json").exists())

    def test_epic_dir_fragments_aggregated(self):
        with TemporaryDirectory() as tmp:
            d = Path(tmp)
            _seed_version_files(d)
            (d / "v0.1.4.json").write_text('{"version":"0.1.4"}')
            _write_fragment(
                d / "epic-99-splines",
                "spline.json",
                {"slug": "spline", "change_type": "feature", "surface": "s", "migration_impact": "m", "agent_notes": "n"},
            )
            rc = cut_release(version=None, releases_dir=d)
            self.assertEqual(rc, 0)
            self.assertTrue((d / "v0.2.0" / "fragments" / "spline.json").exists())
            # Empty epic dir should be cleaned up
            self.assertFalse((d / "epic-99-splines").exists())
            _assert_version_files(d, "0.2.0")

    def test_dry_run_does_not_write(self):
        with TemporaryDirectory() as tmp:
            d = self._make_releases_dir(tmp)
            rc = cut_release(version="v0.2.0", releases_dir=d, dry_run=True)
            self.assertEqual(rc, 0)
            self.assertFalse((d / "v0.2.0").exists())
            self.assertTrue((d / "unreleased" / "cool.json").exists())
            _assert_version_files(d, "0.1.4")

    def test_duplicate_version_returns_error(self):
        with TemporaryDirectory() as tmp:
            d = self._make_releases_dir(tmp)
            cut_release(version="v0.2.0", releases_dir=d)
            # Try again with same version (no fragments left but dir exists)
            _write_fragment(
                d / "unreleased",
                "extra.json",
                {"slug": "extra", "change_type": "docs", "surface": "s", "migration_impact": "m", "agent_notes": "n"},
            )
            rc = cut_release(version="v0.2.0", releases_dir=d)
            self.assertEqual(rc, 1)


# ---------------------------------------------------------------------------
# detect_downstream_baseline (from render_release_migrations.py)
# ---------------------------------------------------------------------------


class DetectDownstreamBaselineTests(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        from render_release_migrations import detect_downstream_baseline
        self.detect = detect_downstream_baseline

    def test_finds_highest_flat_file(self):
        with TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "v0.1.0.json").write_text('{"version":"0.1.0"}')
            (d / "v0.1.3.json").write_text('{"version":"0.1.3"}')
            self.assertEqual(self.detect(d), "0.1.3")

    def test_finds_highest_versioned_dir(self):
        with TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "v0.2.0").mkdir()
            (d / "v0.2.0" / "release.json").write_text("{}")
            self.assertEqual(self.detect(d), "0.2.0")

    def test_empty_dir_returns_none(self):
        with TemporaryDirectory() as tmp:
            d = Path(tmp)
            self.assertIsNone(self.detect(d))


if __name__ == "__main__":
    unittest.main()
