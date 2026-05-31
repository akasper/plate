"""Tests for plate_core.release module."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from plate_core.release import (
    FragmentSummary,
    ReleaseNotesDiffReport,
    ReleaseStatusReport,
    _list_versions,
    _load_pending_fragments,
    _load_release,
    get_release_notes_diff,
    get_release_status,
)
from plate_core.github_client import GhApiError


class ListVersionsTests(unittest.TestCase):
    def test_flat_files(self):
        with TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "v0.1.0.json").write_text('{"version":"0.1.0"}')
            (d / "v0.1.2.json").write_text('{"version":"0.1.2"}')
            (d / "v0.1.1.json").write_text('{"version":"0.1.1"}')
            versions = _list_versions(d)
            self.assertEqual(versions, ["0.1.0", "0.1.1", "0.1.2"])

    def test_versioned_dirs(self):
        with TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "v0.2.0").mkdir()
            (d / "v0.2.0" / "release.json").write_text('{"version":"0.2.0"}')
            (d / "v0.1.3").mkdir()
            (d / "v0.1.3" / "release.json").write_text('{"version":"0.1.3"}')
            versions = _list_versions(d)
            self.assertEqual(versions, ["0.1.3", "0.2.0"])

    def test_mixed_layout(self):
        with TemporaryDirectory() as tmp:
            d = Path(tmp)
            # Legacy flat
            (d / "v0.1.0.json").write_text('{"version":"0.1.0"}')
            # New dir
            (d / "v0.2.0").mkdir()
            (d / "v0.2.0" / "release.json").write_text('{"version":"0.2.0"}')
            versions = _list_versions(d)
            self.assertIn("0.1.0", versions)
            self.assertIn("0.2.0", versions)
            self.assertEqual(versions[0], "0.1.0")
            self.assertEqual(versions[-1], "0.2.0")

    def test_empty_dir(self):
        with TemporaryDirectory() as tmp:
            self.assertEqual(_list_versions(Path(tmp)), [])


class LoadReleaseTests(unittest.TestCase):
    def test_load_flat_file(self):
        with TemporaryDirectory() as tmp:
            d = Path(tmp)
            data = {"version": "0.1.0", "entries": []}
            (d / "v0.1.0.json").write_text(json.dumps(data))
            result = _load_release(d, "0.1.0")
            self.assertEqual(result, data)

    def test_load_versioned_dir(self):
        with TemporaryDirectory() as tmp:
            d = Path(tmp)
            vdir = d / "v0.2.0"
            vdir.mkdir()
            data = {"version": "0.2.0", "entries": []}
            (vdir / "release.json").write_text(json.dumps(data))
            result = _load_release(d, "0.2.0")
            self.assertEqual(result, data)

    def test_load_missing(self):
        with TemporaryDirectory() as tmp:
            result = _load_release(Path(tmp), "9.9.9")
            self.assertIsNone(result)


class LoadPendingFragmentsTests(unittest.TestCase):
    def test_no_unreleased_dir(self):
        with TemporaryDirectory() as tmp:
            frags = _load_pending_fragments(Path(tmp))
            self.assertEqual(frags, [])

    def test_loads_fragments(self):
        with TemporaryDirectory() as tmp:
            d = Path(tmp)
            unreleased = d / "unreleased"
            unreleased.mkdir()
            frag = {
                "slug": "test-feature",
                "change_type": "feature",
                "surface": "some surface",
                "summary": "A test feature",
                "links": ["#42"],
            }
            (unreleased / "test-feature.json").write_text(json.dumps(frag))
            frags = _load_pending_fragments(d)
            self.assertEqual(len(frags), 1)
            self.assertEqual(frags[0].slug, "test-feature")
            self.assertEqual(frags[0].change_type, "feature")
            self.assertEqual(frags[0].links, ["#42"])

    def test_skips_readme(self):
        with TemporaryDirectory() as tmp:
            d = Path(tmp)
            unreleased = d / "unreleased"
            unreleased.mkdir()
            (unreleased / "README.md").write_text("# readme")
            frags = _load_pending_fragments(d)
            self.assertEqual(frags, [])

    def test_skips_malformed_json(self):
        with TemporaryDirectory() as tmp:
            d = Path(tmp)
            unreleased = d / "unreleased"
            unreleased.mkdir()
            (unreleased / "bad.json").write_text("{not valid json}")
            frags = _load_pending_fragments(d)
            self.assertEqual(frags, [])


class GetReleaseNotesDiffTests(unittest.TestCase):
    def _make_releases_dir(self, tmp: str) -> Path:
        d = Path(tmp)
        v010 = {
            "version": "0.1.0",
            "summary": "Initial release",
            "entries": [
                {
                    "change_type": "feature",
                    "surface": "Initial feature",
                    "migration_impact": "None required",
                    "agent_notes": "Nothing to do",
                    "migration_guidance": ["Step 1", "Step 2"],
                }
            ],
        }
        v011 = {
            "version": "0.1.1",
            "summary": "Patch release",
            "entries": [
                {
                    "change_type": "fix",
                    "surface": "Bug fix",
                    "migration_impact": "No change",
                    "agent_notes": "None",
                }
            ],
        }
        (d / "v0.1.0.json").write_text(json.dumps(v010))
        (d / "v0.1.1.json").write_text(json.dumps(v011))
        return d

    def test_all_versions(self):
        with TemporaryDirectory() as tmp:
            d = self._make_releases_dir(tmp)
            report = get_release_notes_diff(releases_dir=d)
            self.assertEqual(report.releases_found, ["0.1.0", "0.1.1"])
            self.assertEqual(len(report.entries), 2)

    def test_from_version_filter(self):
        with TemporaryDirectory() as tmp:
            d = self._make_releases_dir(tmp)
            report = get_release_notes_diff(from_version="0.1.0", releases_dir=d)
            self.assertEqual(report.releases_found, ["0.1.1"])

    def test_to_version_filter(self):
        with TemporaryDirectory() as tmp:
            d = self._make_releases_dir(tmp)
            report = get_release_notes_diff(to_version="0.1.0", releases_dir=d)
            self.assertEqual(report.releases_found, ["0.1.0"])

    def test_migration_steps_extracted(self):
        with TemporaryDirectory() as tmp:
            d = self._make_releases_dir(tmp)
            report = get_release_notes_diff(releases_dir=d)
            self.assertIn("Step 1", report.migration_steps)
            self.assertIn("Step 2", report.migration_steps)

    def test_nonexistent_dir(self):
        report = get_release_notes_diff(releases_dir=Path("/nonexistent/path/xyz"))
        self.assertEqual(report.releases_found, [])
        self.assertEqual(report.entries, [])

    def test_to_dict(self):
        with TemporaryDirectory() as tmp:
            d = self._make_releases_dir(tmp)
            report = get_release_notes_diff(releases_dir=d)
            d_out = report.to_dict()
            self.assertIn("releases_found", d_out)
            self.assertIn("entries", d_out)
            self.assertIn("migration_steps", d_out)


class GetReleaseStatusTests(unittest.TestCase):
    def test_basic_status_no_release_branch(self):
        with TemporaryDirectory() as tmp:
            d = Path(tmp)
            unreleased = d / "unreleased"
            unreleased.mkdir()
            frag = {
                "slug": "my-feat",
                "change_type": "feature",
                "surface": "test",
                "summary": "A feature",
                "links": [],
            }
            (unreleased / "my-feat.json").write_text(json.dumps(frag))

            client = Mock()
            # release branch check raises → not found
            client.api.side_effect = [
                GhApiError("Not Found"),  # branches/release
                {"items": [], "total_count": 0},  # open Release issues
            ]

            with patch("plate_core.release.resolve_repo", return_value="owner/repo"):
                report = get_release_status(repo="owner/repo", releases_dir=d, client=client)

            self.assertFalse(report.release_branch_exists)
            self.assertEqual(report.pending_fragment_count, 1)
            self.assertEqual(report.pending_fragments[0].slug, "my-feat")

    def test_release_branch_present(self):
        with TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "v0.1.3.json").write_text('{"version":"0.1.3","entries":[]}')

            client = Mock()
            client.api.side_effect = [
                {"name": "release"},  # branches/release → exists
                {"items": [{"number": 10, "title": "Release v0.2.0", "html_url": "https://..."}], "total_count": 1},
            ]

            with patch("plate_core.release.resolve_repo", return_value="owner/repo"):
                report = get_release_status(repo="owner/repo", releases_dir=d, client=client)

            self.assertTrue(report.release_branch_exists)
            self.assertEqual(report.latest_version, "0.1.3")
            self.assertEqual(len(report.open_release_issues), 1)

    def test_to_dict_schema(self):
        report = ReleaseStatusReport(
            repo="owner/repo",
            release_branch_exists=True,
            open_release_issues=[],
            current_version="0.1.3",
            latest_version="0.1.3",
            pending_fragment_count=0,
            pending_fragments=[],
            extension_release_checks=[],
        )
        d = report.to_dict()
        self.assertIn("release_branch_exists", d)
        self.assertIn("pending_fragments", d)
        self.assertIn("extension_release_checks", d)


if __name__ == "__main__":
    unittest.main()
