"""Tests for plate_core.release module."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from plate_core.version_sync import read_repository_versions
from plate_core.release import (
    FragmentSummary,
    ReleaseNotesDiffReport,
    ReleaseStatusReport,
    ReleaseTargetEpicGuidance,
    _list_versions,
    _load_pending_fragments,
    _load_release,
    cut_release,
    cleanup_dead_branches,
    get_release_notes_diff,
    get_release_status,
    get_release_target_epic_guidance,
    validate_release_workspace,
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


def _seed_version_files(repo_root: Path, version: str = "0.1.4") -> None:
    (repo_root / "src" / "plate_core").mkdir(parents=True, exist_ok=True)
    (repo_root / "plugin").mkdir(parents=True, exist_ok=True)
    (repo_root / ".plugin").mkdir(parents=True, exist_ok=True)
    (repo_root / ".github" / "plugin").mkdir(parents=True, exist_ok=True)
    (repo_root / ".grok-plugin").mkdir(parents=True, exist_ok=True)
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
    (repo_root / ".grok-plugin" / "marketplace.json").write_text(
        json.dumps(
            {
                "name": "plate-marketplace",
                "plugins": [{"name": "plate-core", "source": {"type": "local", "path": "./.plugin"}, "version": version}],
            }
        ),
        encoding="utf-8",
    )

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


class CutReleaseVersionSyncTests(unittest.TestCase):
    def test_core_cut_release_syncs_package_and_plugin_versions(self):
        with TemporaryDirectory() as tmp:
            d = Path(tmp)
            _seed_version_files(d)
            (d / "v0.1.4.json").write_text('{"version":"0.1.4"}')
            unreleased = d / "unreleased"
            unreleased.mkdir()
            (unreleased / "cool.json").write_text(
                json.dumps(
                    {
                        "slug": "cool",
                        "change_type": "feature",
                        "surface": "s",
                        "migration_impact": "m",
                        "agent_notes": "n",
                    }
                ),
                encoding="utf-8",
            )

            rc = cut_release(version=None, releases_dir=d)

            self.assertEqual(rc, 0)
            self.assertIn('__version__ = "0.2.0"', (d / "src" / "plate_core" / "__init__.py").read_text(encoding="utf-8"))
            self.assertIn('version = "0.2.0"', (d / "pyproject.toml").read_text(encoding="utf-8"))
            self.assertEqual(
                json.loads((d / "plugin" / "plugin.json").read_text(encoding="utf-8"))["version"],
                "0.2.0",
            )
            self.assertEqual(
                json.loads((d / ".plugin" / "plugin.json").read_text(encoding="utf-8"))["version"],
                "0.2.0",
            )
            marketplace = json.loads((d / ".github" / "plugin" / "marketplace.json").read_text(encoding="utf-8"))
            self.assertEqual(marketplace["metadata"]["version"], "0.2.0")
            self.assertEqual(marketplace["plugins"][0]["version"], "0.2.0")
            grok_marketplace = json.loads((d / ".grok-plugin" / "marketplace.json").read_text(encoding="utf-8"))
            self.assertEqual(grok_marketplace["plugins"][0]["version"], "0.2.0")


class VersionSyncReadTests(unittest.TestCase):
    def test_read_repository_versions_rejects_duplicate_version_lines(self):
        with TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            _seed_version_files(repo_root, version="0.5.0")
            runtime = repo_root / "src" / "plate_core" / "__init__.py"
            runtime.write_text(
                '"""plate_core runtime package."""\n\n__version__ = "0.5.0"\n__version__ = "0.5.1"\n',
                encoding="utf-8",
            )

            with self.assertRaisesRegex(RuntimeError, "Expected exactly one version field"):
                read_repository_versions(repo_root)


class ReleaseWorkspaceValidationTests(unittest.TestCase):
    def test_validation_passes_for_synced_version_files_and_release_artifact(self):
        with TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            _seed_version_files(repo_root, version="0.5.0")
            versioned_release = repo_root / ".agentic" / "releases" / "v0.5.0"
            versioned_release.mkdir(parents=True)
            (versioned_release / "release.json").write_text(
                json.dumps({"version": "0.5.0", "entries": []}),
                encoding="utf-8",
            )

            report = validate_release_workspace(repo_root)

            self.assertEqual(report.release_version, "0.5.0")
            self.assertEqual(report.release_tag, "v0.5.0")
            self.assertEqual(report.release_file, ".agentic/releases/v0.5.0/release.json")
            self.assertEqual(report.release_file_version, "0.5.0")
            self.assertEqual(report.errors, [])

    def test_validation_detects_out_of_sync_version_files(self):
        with TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            _seed_version_files(repo_root, version="0.5.0")
            plugin_manifest_path = repo_root / "plugin" / "plugin.json"
            plugin_manifest = json.loads(plugin_manifest_path.read_text(encoding="utf-8"))
            plugin_manifest["version"] = "0.5.1"
            plugin_manifest_path.write_text(json.dumps(plugin_manifest), encoding="utf-8")

            report = validate_release_workspace(repo_root)

            self.assertIsNone(report.release_version)
            self.assertIsNone(report.release_tag)
            self.assertEqual(report.release_file, None)
            self.assertTrue(any("Repository version files are not in sync" in error for error in report.errors))

    def test_validation_requires_matching_release_artifact(self):
        with TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            _seed_version_files(repo_root, version="0.5.0")
            versioned_release = repo_root / ".agentic" / "releases" / "v0.5.0"
            versioned_release.mkdir(parents=True)
            (versioned_release / "release.json").write_text(
                json.dumps({"version": "0.4.9", "entries": []}),
                encoding="utf-8",
            )

            report = validate_release_workspace(repo_root)

            self.assertEqual(report.release_version, "0.5.0")
            self.assertEqual(report.release_file_version, "0.4.9")
            self.assertTrue(
                any("does not match synced repository version" in error for error in report.errors),
                report.errors,
            )

    def test_validation_rejects_invalid_semver_without_follow_on_release_artifact_probe(self):
        with TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            _seed_version_files(repo_root, version="0.5.0")
            pyproject = repo_root / "pyproject.toml"
            pyproject.write_text(
                "\n".join(
                    [
                        "[project]",
                        'name = "plate-core"',
                        'version = "../oops"',
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            (repo_root / "plugin" / "plugin.json").write_text(
                json.dumps({"name": "plate-core", "version": "../oops", "repository": "https://github.com/akasper/plate"}),
                encoding="utf-8",
            )
            (repo_root / ".plugin" / "plugin.json").write_text(
                json.dumps({"name": "plate-core", "version": "../oops", "repository": "https://github.com/akasper/plate"}),
                encoding="utf-8",
            )
            (repo_root / ".github" / "plugin" / "marketplace.json").write_text(
                json.dumps(
                    {
                        "name": "plate-marketplace",
                        "metadata": {"version": "../oops"},
                        "plugins": [{"name": "plate-core", "source": "plugin", "version": "../oops"}],
                    }
                ),
                encoding="utf-8",
            )
            (repo_root / ".grok-plugin" / "marketplace.json").write_text(
                json.dumps(
                    {
                        "name": "plate-marketplace",
                        "plugins": [{"name": "plate-core", "source": {"type": "local", "path": "./.plugin"}, "version": "../oops"}],
                    }
                ),
                encoding="utf-8",
            )
            (repo_root / "src" / "plate_core" / "__init__.py").write_text(
                '"""plate_core runtime package."""\n\n__version__ = "../oops"\n',
                encoding="utf-8",
            )

            report = validate_release_workspace(repo_root)

            self.assertEqual(report.release_version, "../oops")
            self.assertIn("Repository version '../oops' is not valid semver.", report.errors)
            self.assertEqual(report.release_file, None)
            self.assertEqual(report.release_file_version, None)
            self.assertEqual(len(report.errors), 1)


class VersionSyncReadTests(unittest.TestCase):
    def test_read_repository_versions_rejects_duplicate_version_lines(self):
        with TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            _seed_version_files(repo_root, version="0.5.0")
            runtime = repo_root / "src" / "plate_core" / "__init__.py"
            runtime.write_text(
                '"""plate_core runtime package."""\n\n__version__ = "0.5.0"\n__version__ = "0.5.1"\n',
                encoding="utf-8",
            )

            with self.assertRaisesRegex(RuntimeError, "Expected exactly one version field"):
                read_repository_versions(repo_root)


class ReleaseWorkspaceValidationTests(unittest.TestCase):
    def test_validation_passes_for_synced_version_files_and_release_artifact(self):
        with TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            _seed_version_files(repo_root, version="0.5.0")
            versioned_release = repo_root / ".agentic" / "releases" / "v0.5.0"
            versioned_release.mkdir(parents=True)
            (versioned_release / "release.json").write_text(
                json.dumps({"version": "0.5.0", "entries": []}),
                encoding="utf-8",
            )

            report = validate_release_workspace(repo_root)

            self.assertEqual(report.release_version, "0.5.0")
            self.assertEqual(report.release_tag, "v0.5.0")
            self.assertEqual(report.release_file, ".agentic/releases/v0.5.0/release.json")
            self.assertEqual(report.release_file_version, "0.5.0")
            self.assertEqual(report.errors, [])

    def test_validation_detects_out_of_sync_version_files(self):
        with TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            _seed_version_files(repo_root, version="0.5.0")
            plugin_manifest_path = repo_root / "plugin" / "plugin.json"
            plugin_manifest = json.loads(plugin_manifest_path.read_text(encoding="utf-8"))
            plugin_manifest["version"] = "0.5.1"
            plugin_manifest_path.write_text(json.dumps(plugin_manifest), encoding="utf-8")

            report = validate_release_workspace(repo_root)

            self.assertIsNone(report.release_version)
            self.assertIsNone(report.release_tag)
            self.assertEqual(report.release_file, None)
            self.assertTrue(any("Repository version files are not in sync" in error for error in report.errors))

    def test_validation_requires_matching_release_artifact(self):
        with TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            _seed_version_files(repo_root, version="0.5.0")
            versioned_release = repo_root / ".agentic" / "releases" / "v0.5.0"
            versioned_release.mkdir(parents=True)
            (versioned_release / "release.json").write_text(
                json.dumps({"version": "0.4.9", "entries": []}),
                encoding="utf-8",
            )

            report = validate_release_workspace(repo_root)

            self.assertEqual(report.release_version, "0.5.0")
            self.assertEqual(report.release_file_version, "0.4.9")
            self.assertTrue(
                any("does not match synced repository version" in error for error in report.errors),
                report.errors,
            )

    def test_validation_rejects_invalid_semver_without_follow_on_release_artifact_probe(self):
        with TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            _seed_version_files(repo_root, version="0.5.0")
            pyproject = repo_root / "pyproject.toml"
            pyproject.write_text(
                "\n".join(
                    [
                        "[project]",
                        'name = "plate-core"',
                        'version = "../oops"',
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            (repo_root / "plugin" / "plugin.json").write_text(
                json.dumps({"name": "plate-core", "version": "../oops", "repository": "https://github.com/akasper/plate"}),
                encoding="utf-8",
            )
            (repo_root / ".plugin" / "plugin.json").write_text(
                json.dumps({"name": "plate-core", "version": "../oops", "repository": "https://github.com/akasper/plate"}),
                encoding="utf-8",
            )
            (repo_root / ".github" / "plugin" / "marketplace.json").write_text(
                json.dumps(
                    {
                        "metadata": {"version": "../oops"},
                        "plugins": [
                            {
                                "name": "plate-core",
                                "description": "PLATE core plugin",
                                "version": "../oops",
                                "repository": "https://github.com/akasper/plate",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            (repo_root / ".grok-plugin" / "marketplace.json").write_text(
                json.dumps(
                    {
                        "plugins": [
                            {
                                "name": "plate-core",
                                "version": "../oops",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            (repo_root / "src" / "plate_core" / "__init__.py").write_text(
                '"""plate_core runtime package."""\n\n__version__ = "../oops"\n',
                encoding="utf-8",
            )

            report = validate_release_workspace(repo_root)

            self.assertEqual(report.release_version, "../oops")
            self.assertIn("Repository version '../oops' is not valid semver.", report.errors)
            self.assertEqual(report.release_file, None)
            self.assertEqual(report.release_file_version, None)
            self.assertEqual(len(report.errors), 1)


class VersionSyncReadTests(unittest.TestCase):
    def test_read_repository_versions_rejects_duplicate_version_lines(self):
        with TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            _seed_version_files(repo_root, version="0.5.0")
            runtime = repo_root / "src" / "plate_core" / "__init__.py"
            runtime.write_text(
                '"""plate_core runtime package."""\n\n__version__ = "0.5.0"\n__version__ = "0.5.1"\n',
                encoding="utf-8",
            )

            with self.assertRaisesRegex(RuntimeError, "Expected exactly one version field"):
                read_repository_versions(repo_root)


class ReleaseWorkspaceValidationTests(unittest.TestCase):
    def test_validation_passes_for_synced_version_files_and_release_artifact(self):
        with TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            _seed_version_files(repo_root, version="0.5.0")
            versioned_release = repo_root / ".agentic" / "releases" / "v0.5.0"
            versioned_release.mkdir(parents=True)
            (versioned_release / "release.json").write_text(
                json.dumps({"version": "0.5.0", "entries": []}),
                encoding="utf-8",
            )

            report = validate_release_workspace(repo_root)

            self.assertEqual(report.release_version, "0.5.0")
            self.assertEqual(report.release_tag, "v0.5.0")
            self.assertEqual(report.release_file, ".agentic/releases/v0.5.0/release.json")
            self.assertEqual(report.release_file_version, "0.5.0")
            self.assertEqual(report.errors, [])

    def test_validation_detects_out_of_sync_version_files(self):
        with TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            _seed_version_files(repo_root, version="0.5.0")
            plugin_manifest_path = repo_root / "plugin" / "plugin.json"
            plugin_manifest = json.loads(plugin_manifest_path.read_text(encoding="utf-8"))
            plugin_manifest["version"] = "0.5.1"
            plugin_manifest_path.write_text(json.dumps(plugin_manifest), encoding="utf-8")

            report = validate_release_workspace(repo_root)

            self.assertIsNone(report.release_version)
            self.assertIsNone(report.release_tag)
            self.assertEqual(report.release_file, None)
            self.assertTrue(any("Repository version files are not in sync" in error for error in report.errors))

    def test_validation_requires_matching_release_artifact(self):
        with TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            _seed_version_files(repo_root, version="0.5.0")
            versioned_release = repo_root / ".agentic" / "releases" / "v0.5.0"
            versioned_release.mkdir(parents=True)
            (versioned_release / "release.json").write_text(
                json.dumps({"version": "0.4.9", "entries": []}),
                encoding="utf-8",
            )

            report = validate_release_workspace(repo_root)

            self.assertEqual(report.release_version, "0.5.0")
            self.assertEqual(report.release_file_version, "0.4.9")
            self.assertTrue(
                any("does not match synced repository version" in error for error in report.errors),
                report.errors,
            )

    def test_validation_rejects_invalid_semver_without_follow_on_release_artifact_probe(self):
        with TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            _seed_version_files(repo_root, version="0.5.0")
            pyproject = repo_root / "pyproject.toml"
            pyproject.write_text(
                "\n".join(
                    [
                        "[project]",
                        'name = "plate-core"',
                        'version = "../oops"',
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            (repo_root / "plugin" / "plugin.json").write_text(
                json.dumps({"name": "plate-core", "version": "../oops", "repository": "https://github.com/akasper/plate"}),
                encoding="utf-8",
            )
            (repo_root / ".plugin" / "plugin.json").write_text(
                json.dumps({"name": "plate-core", "version": "../oops", "repository": "https://github.com/akasper/plate"}),
                encoding="utf-8",
            )
            (repo_root / ".github" / "plugin" / "marketplace.json").write_text(
                json.dumps(
                    {
                        "name": "plate-marketplace",
                        "metadata": {"version": "../oops"},
                        "plugins": [{"name": "plate-core", "source": "plugin", "version": "../oops"}],
                    }
                ),
                encoding="utf-8",
            )
            (repo_root / ".grok-plugin" / "marketplace.json").write_text(
                json.dumps(
                    {
                        "name": "plate-marketplace",
                        "plugins": [{"name": "plate-core", "source": {"type": "local", "path": "./.plugin"}, "version": "../oops"}],
                    }
                ),
                encoding="utf-8",
            )
            (repo_root / "src" / "plate_core" / "__init__.py").write_text(
                '"""plate_core runtime package."""\n\n__version__ = "../oops"\n',
                encoding="utf-8",
            )

            report = validate_release_workspace(repo_root)

            self.assertEqual(report.release_version, "../oops")
            self.assertIn("Repository version '../oops' is not valid semver.", report.errors)
            self.assertEqual(report.release_file, None)
            self.assertEqual(report.release_file_version, None)
            self.assertEqual(len(report.errors), 1)


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
            def api_side_effect(endpoint, method="GET", fields=None, retries=3, base_backoff=0.5):
                if endpoint.startswith("repos/owner/repo/branches/"):
                    raise GhApiError("Not Found")
                if endpoint.startswith("search/issues?q=") and "label%3ARelease" in endpoint:
                    return {"items": [], "total_count": 0}
                if endpoint.startswith("search/issues?q=") and "label%3AMajor" in endpoint:
                    return {"items": [], "total_count": 0}
                raise AssertionError(f"Unexpected endpoint: {endpoint}")

            client.api.side_effect = api_side_effect

            with patch("plate_core.release.resolve_repo", return_value="owner/repo"):
                report = get_release_status(repo="owner/repo", releases_dir=d, client=client)

            self.assertFalse(report.release_branch_exists)
            self.assertEqual(report.release_branch_mode, "none")
            self.assertEqual(report.release_track_branches["release"], False)
            self.assertEqual(report.release_branch_reset_target, "main")
            self.assertGreaterEqual(len(report.warnings), 1)
            self.assertEqual(report.pending_fragment_count, 1)
            self.assertEqual(report.pending_fragments[0].slug, "my-feat")

    def test_release_branch_present(self):
        with TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "v0.1.3.json").write_text('{"version":"0.1.3","entries":[]}')

            client = Mock()
            def api_side_effect(endpoint, method="GET", fields=None, retries=3, base_backoff=0.5):
                if endpoint == "repos/owner/repo/branches/release":
                    return {"name": "release"}
                if endpoint.startswith("repos/owner/repo/branches/"):
                    raise GhApiError("Not Found")
                if endpoint.startswith("search/issues?q=") and "label%3ARelease" in endpoint:
                    return {"items": [{"number": 10, "title": "Release v0.2.0", "html_url": "https://..."}], "total_count": 1}
                if endpoint.startswith("search/issues?q=") and "label%3AMajor" in endpoint:
                    return {"items": [], "total_count": 0}
                raise AssertionError(f"Unexpected endpoint: {endpoint}")

            client.api.side_effect = api_side_effect

            with patch("plate_core.release.resolve_repo", return_value="owner/repo"):
                report = get_release_status(repo="owner/repo", releases_dir=d, client=client)

            self.assertTrue(report.release_branch_exists)
            self.assertEqual(report.release_branch_mode, "legacy")
            self.assertEqual(report.release_track_branches["release-major"], False)
            self.assertEqual(report.release_branch_reset_target, "main")
            self.assertGreaterEqual(len(report.warnings), 1)
            self.assertEqual(report.latest_version, "0.1.3")
            self.assertEqual(len(report.open_release_issues), 1)

    def test_to_dict_schema(self):
        report = ReleaseStatusReport(
            repo="owner/repo",
            release_branch_exists=True,
            release_track_branches={},
            release_branch_mode="legacy",
            release_branch_reset_target="main",
            warnings=[],
            open_release_issues=[],
            current_version="0.1.3",
            latest_version="0.1.3",
            pending_fragment_count=0,
            pending_fragments=[],
            extension_release_checks=[],
            active_next_release=None,
            linked_epics=[],
            on_hold_epics=[],
            release_track_summary={},
        )
        d = report.to_dict()
        self.assertIn("release_branch_exists", d)
        self.assertIn("release_track_branches", d)
        self.assertIn("release_branch_mode", d)
        self.assertIn("release_branch_reset_target", d)
        self.assertIn("warnings", d)
        self.assertIn("pending_fragments", d)
        self.assertIn("extension_release_checks", d)
        self.assertIn("active_next_release", d)
        self.assertIn("linked_epics", d)
        self.assertIn("on_hold_epics", d)
        self.assertIn("release_track_summary", d)

    def test_status_populates_next_release_linked_epics_and_on_hold(self):
        with TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "v0.1.3.json").write_text('{"version":"0.1.3","entries":[]}')

            client = Mock()

            def api_side_effect(endpoint, method="GET", fields=None, retries=3, base_backoff=0.5):
                if endpoint in {
                    "repos/owner/repo/branches/release",
                    "repos/owner/repo/branches/release-major",
                    "repos/owner/repo/branches/release-minor",
                    "repos/owner/repo/branches/release-patch",
                }:
                    return {"name": "release"}
                if endpoint.startswith("search/issues?q=") and "label%3ARelease" in endpoint:
                    return {
                        "items": [
                            {
                                "number": 50,
                                "title": "Next Release",
                                "html_url": "https://github.com/owner/repo/issues/50",
                            }
                        ],
                        "total_count": 1,
                    }
                if endpoint == "graphql":
                    return {
                        "data": {
                            "repository": {
                                "issue": {
                                    "closingIssuesReferences": {
                                        "nodes": [
                                            {
                                                "number": 306,
                                                "title": "Targeted epic",
                                                "url": "https://github.com/owner/repo/issues/306",
                                                "labels": {"nodes": [{"name": "Epic"}, {"name": "Minor"}]},
                                            }
                                        ]
                                    },
                                    "timelineItems": {
                                        "nodes": [
                                            {
                                                "subject": {
                                                    "__typename": "Issue",
                                                    "number": 306,
                                                    "title": "Targeted epic",
                                                    "url": "https://github.com/owner/repo/issues/306",
                                                    "labels": {"nodes": [{"name": "Epic"}, {"name": "Minor"}]},
                                                }
                                            }
                                        ]
                                    },
                                }
                            }
                        }
                    }
                if endpoint.startswith("search/issues?q=") and "label%3AMajor" in endpoint:
                    return {
                        "items": [
                            {
                                "number": 306,
                                "title": "Targeted epic",
                                "html_url": "https://github.com/owner/repo/issues/306",
                                "labels": [{"name": "Epic"}, {"name": "Minor"}],
                            },
                            {
                                "number": 307,
                                "title": "On-hold epic",
                                "html_url": "https://github.com/owner/repo/issues/307",
                                "labels": [{"name": "Epic"}, {"name": "Patch"}],
                            },
                            {
                                "number": 308,
                                "title": "Tracked feature",
                                "html_url": "https://github.com/owner/repo/issues/308",
                                "labels": [{"name": "Feature"}, {"name": "Major"}],
                            },
                        ],
                        "total_count": 3,
                    }
                raise AssertionError(f"Unexpected endpoint: {endpoint}")

            client.api.side_effect = api_side_effect

            with patch("plate_core.release.resolve_repo", return_value="owner/repo"):
                report = get_release_status(repo="owner/repo", releases_dir=d, client=client)

            self.assertEqual(report.active_next_release["number"], 50)
            self.assertEqual(report.active_next_release["html_url"], "https://github.com/owner/repo/issues/50")
            self.assertEqual(report.release_branch_mode, "multi-track")
            self.assertEqual(report.release_branch_reset_target, "main")
            self.assertEqual(report.warnings, [])
            self.assertEqual(
                report.linked_epics,
                [
                    {
                        "number": 306,
                        "title": "Targeted epic",
                        "html_url": "https://github.com/owner/repo/issues/306",
                        "labels": ["Epic", "Minor"],
                    }
                ],
            )
            self.assertEqual(
                report.on_hold_epics,
                [
                    {
                        "number": 307,
                        "title": "On-hold epic",
                        "html_url": "https://github.com/owner/repo/issues/307",
                        "labels": ["Epic", "Patch"],
                    }
                ],
            )
            self.assertEqual(report.release_track_summary, {"Major": 1, "Minor": 1, "Patch": 1})

    def test_status_marks_track_labeled_epics_on_hold_without_active_next_release(self):
        with TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "v0.1.3.json").write_text('{"version":"0.1.3","entries":[]}')

            client = Mock()

            def api_side_effect(endpoint, method="GET", fields=None, retries=3, base_backoff=0.5):
                if endpoint in {
                    "repos/owner/repo/branches/release",
                    "repos/owner/repo/branches/release-major",
                    "repos/owner/repo/branches/release-minor",
                    "repos/owner/repo/branches/release-patch",
                }:
                    return {"name": "release"}
                if endpoint.startswith("search/issues?q=") and "label%3ARelease" in endpoint:
                    return {"items": [], "total_count": 0}
                if endpoint.startswith("search/issues?q=") and "label%3AMajor" in endpoint:
                    return {
                        "items": [
                            {
                                "number": 401,
                                "title": "Track epic without active next",
                                "html_url": "https://github.com/owner/repo/issues/401",
                                "labels": [{"name": "Epic"}, {"name": "Minor"}],
                            }
                        ],
                        "total_count": 1,
                    }
                raise AssertionError(f"Unexpected endpoint: {endpoint}")

            client.api.side_effect = api_side_effect

            with patch("plate_core.release.resolve_repo", return_value="owner/repo"):
                report = get_release_status(repo="owner/repo", releases_dir=d, client=client)

            self.assertEqual(report.active_next_release, None)
            self.assertEqual(
                report.on_hold_epics,
                [
                    {
                        "number": 401,
                        "title": "Track epic without active next",
                        "html_url": "https://github.com/owner/repo/issues/401",
                        "labels": ["Epic", "Minor"],
                    }
                ],
            )

    def test_status_reports_hybrid_mode_when_track_branches_are_partial(self):
        with TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "v0.1.3.json").write_text('{"version":"0.1.3","entries":[]}')

            client = Mock()

            def api_side_effect(endpoint, method="GET", fields=None, retries=3, base_backoff=0.5):
                if endpoint in {"repos/owner/repo/branches/release", "repos/owner/repo/branches/release-major"}:
                    return {"name": "release"}
                if endpoint in {"repos/owner/repo/branches/release-minor", "repos/owner/repo/branches/release-patch"}:
                    raise GhApiError("Not Found")
                if endpoint.startswith("search/issues?q=") and "label%3ARelease" in endpoint:
                    return {"items": [], "total_count": 0}
                if endpoint.startswith("search/issues?q=") and "label%3AMajor" in endpoint:
                    return {"items": [], "total_count": 0}
                raise AssertionError(f"Unexpected endpoint: {endpoint}")

            client.api.side_effect = api_side_effect

            with patch("plate_core.release.resolve_repo", return_value="owner/repo"):
                report = get_release_status(repo="owner/repo", releases_dir=d, client=client)

            self.assertEqual(report.release_branch_mode, "hybrid")
            self.assertEqual(report.release_track_branches["release"], True)
            self.assertEqual(report.release_track_branches["release-major"], True)
            self.assertEqual(report.release_track_branches["release-minor"], False)
            self.assertEqual(report.release_track_branches["release-patch"], False)
            self.assertGreaterEqual(len(report.warnings), 1)


class ReleaseTargetEpicGuidanceTests(unittest.TestCase):
    def test_guidance_returns_manual_steps_for_epic_and_next_release(self):
        client = Mock()
        client.api.return_value = {
            "number": 306,
            "title": "Release ceremony refinement",
            "html_url": "https://github.com/owner/repo/issues/306",
            "labels": [{"name": "Epic"}, {"name": "Minor"}],
        }
        status = ReleaseStatusReport(
            repo="owner/repo",
            release_branch_exists=True,
            release_track_branches={"release": True, "release-major": True, "release-minor": True, "release-patch": True},
            release_branch_mode="multi-track",
            release_branch_reset_target="main",
            warnings=[],
            open_release_issues=[{"number": 50, "title": "Next Release", "html_url": "https://github.com/owner/repo/issues/50"}],
            current_version="0.1.3",
            latest_version="0.1.3",
            pending_fragment_count=0,
            pending_fragments=[],
            extension_release_checks=[],
            active_next_release={"number": 50, "title": "Next Release", "html_url": "https://github.com/owner/repo/issues/50"},
            linked_epics=[],
            on_hold_epics=[],
            release_track_summary={"Major": 0, "Minor": 1, "Patch": 0},
        )

        with patch("plate_core.release.resolve_repo", return_value="owner/repo"):
            with patch("plate_core.release.get_release_status", return_value=status):
                guidance = get_release_target_epic_guidance(epic_number=306, repo="owner/repo", client=client)

        self.assertTrue(guidance.can_target)
        self.assertFalse(guidance.api_write_supported)
        self.assertEqual(guidance.epic["number"], 306)
        self.assertEqual(guidance.active_next_release["number"], 50)
        self.assertIn("GitHub's public API does not support", guidance.message)
        self.assertEqual(len(guidance.manual_steps), 4)


class CleanupDeadBranchesTests(unittest.TestCase):
    def test_cleanup_dead_branches_dry_run(self):
        client = Mock()

        def api_side_effect(endpoint, method="GET", fields=None, retries=3, base_backoff=0.5):
            if endpoint == "repos/owner/repo":
                return {"default_branch": "main"}
            if endpoint == "repos/owner/repo/branches?per_page=100&page=1":
                return [
                    {"name": "main", "protected": True},
                    {"name": "release", "protected": False},
                    {"name": "release-minor", "protected": False},
                    {"name": "feature-merged", "protected": False},
                    {"name": "feature-open-pr", "protected": False},
                    {"name": "feature-unmerged", "protected": False},
                    {"name": "protected-branch", "protected": True},
                ]
            if endpoint == "repos/owner/repo/branches?per_page=100&page=2":
                return []
            if endpoint == "repos/owner/repo/pulls?state=open&head=owner:feature-merged&per_page=1":
                return []
            if endpoint == "repos/owner/repo/pulls?state=open&head=owner:feature-open-pr&per_page=1":
                return [{"number": 101}]
            if endpoint == "repos/owner/repo/pulls?state=open&head=owner:feature-unmerged&per_page=1":
                return []
            if endpoint == "repos/owner/repo/compare/main...feature-merged":
                return {"status": "behind", "ahead_by": 0}
            if endpoint == "repos/owner/repo/compare/main...feature-unmerged":
                return {"status": "ahead", "ahead_by": 2}
            raise AssertionError(f"Unexpected endpoint: {endpoint}")

        client.api.side_effect = api_side_effect
        with patch("plate_core.release.resolve_repo", return_value="owner/repo"):
            report = cleanup_dead_branches(repo="owner/repo", client=client)

        self.assertEqual(report.base_branch, "main")
        self.assertFalse(report.apply)
        self.assertEqual(report.candidates, ["feature-merged"])
        self.assertEqual(report.skipped_open_pr, ["feature-open-pr"])
        self.assertEqual(report.skipped_not_merged, ["feature-unmerged"])
        self.assertEqual(report.deleted, [])

    def test_cleanup_dead_branches_apply_with_failure(self):
        client = Mock()

        def api_side_effect(endpoint, method="GET", fields=None, retries=3, base_backoff=0.5):
            if endpoint == "repos/owner/repo":
                return {"default_branch": "main"}
            if endpoint == "repos/owner/repo/branches?per_page=100&page=1":
                return [
                    {"name": "feature-merged-a", "protected": False},
                    {"name": "feature-merged-b", "protected": False},
                ]
            if endpoint == "repos/owner/repo/branches?per_page=100&page=2":
                return []
            if endpoint in {
                "repos/owner/repo/pulls?state=open&head=owner:feature-merged-a&per_page=1",
                "repos/owner/repo/pulls?state=open&head=owner:feature-merged-b&per_page=1",
            }:
                return []
            if endpoint in {
                "repos/owner/repo/compare/main...feature-merged-a",
                "repos/owner/repo/compare/main...feature-merged-b",
            }:
                return {"status": "behind", "ahead_by": 0}
            if endpoint == "repos/owner/repo/git/refs/heads/feature-merged-a" and method == "DELETE":
                return {}
            if endpoint == "repos/owner/repo/git/refs/heads/feature-merged-b" and method == "DELETE":
                raise GhApiError("delete failed")
            raise AssertionError(f"Unexpected endpoint: {endpoint} ({method})")

        client.api.side_effect = api_side_effect
        with patch("plate_core.release.resolve_repo", return_value="owner/repo"):
            report = cleanup_dead_branches(
                repo="owner/repo",
                apply=True,
                client=client,
            )

        self.assertTrue(report.apply)
        self.assertEqual(report.candidates, ["feature-merged-a", "feature-merged-b"])
        self.assertEqual(report.deleted, ["feature-merged-a"])
        self.assertEqual(len(report.failed), 1)
        self.assertEqual(report.failed[0]["branch"], "feature-merged-b")


if __name__ == "__main__":
    unittest.main()
