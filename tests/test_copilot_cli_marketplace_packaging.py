import json
import unittest
from pathlib import Path

from plate_core import __version__


REPO_ROOT = Path(__file__).resolve().parents[1]


def read_text(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def read_json(relative_path: str) -> dict:
    return json.loads(read_text(relative_path))


class CopilotCliMarketplacePackagingTests(unittest.TestCase):
    def test_marketplace_manifest_points_at_plugin_surface(self):
        manifest = read_json(".github/plugin/marketplace.json")

        self.assertEqual(manifest["name"], "plate-marketplace")
        self.assertEqual(manifest["metadata"]["version"], __version__)
        self.assertEqual(len(manifest["plugins"]), 1)

        plugin_entry = manifest["plugins"][0]
        plugin_manifest = read_json(f"{plugin_entry['source']}/plugin.json")
        root_plugin_manifest = read_json(".plugin/plugin.json")

        self.assertEqual(plugin_entry["name"], "plate-core")
        self.assertEqual(plugin_entry["source"], "plugin")
        self.assertEqual(plugin_entry["version"], __version__)
        self.assertEqual(plugin_manifest["name"], plugin_entry["name"])
        self.assertEqual(plugin_manifest["version"], __version__)
        self.assertEqual(root_plugin_manifest["version"], __version__)
        self.assertEqual(plugin_manifest["repository"], plugin_entry["repository"])

    def test_readme_documents_prelaunch_marketplace_install_flow(self):
        readme = read_text("README.md")

        self.assertIn("copilot plugin marketplace add akasper/plate", readme)
        self.assertIn("copilot plugin install plate-core@plate-marketplace", readme)
        self.assertIn("pip install plate-core", readme)
        self.assertIn("There is no separate GitHub-run submission process for Copilot CLI marketplaces", readme)
        self.assertIn("Marketplace release checklist", readme)
        self.assertIn("Complete the human-owned publication tasks tracked in #380 and #381.", readme)

    def test_ci_uses_repo_marketplace_as_prelaunch_surface(self):
        workflow = read_text(".github/workflows/ci.yml")

        self.assertIn("Plugin install smoke test (pre-launch marketplace surface)", workflow)
        # Note: the conditional if (only on main push) was removed in #375 to run the
        # supported marketplace smoke unconditionally on all PRs (prevents hangs from
        # deprecated direct installs and provides early validation).
        self.assertIn("copilot plugin marketplace add akasper/plate", workflow)
        self.assertIn("copilot plugin install plate-core@plate-marketplace", workflow)
        self.assertIn("copilot plugin marketplace remove plate-marketplace --force", workflow)


if __name__ == "__main__":
    unittest.main()
