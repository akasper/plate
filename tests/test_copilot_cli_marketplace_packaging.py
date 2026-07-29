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
        self.assertEqual(plugin_manifest.get("skills"), "skills/")

    def test_plugin_mcp_manifest_uses_grok_runtime_wrapper(self):
        for surface in ("plugin", ".plugin"):
            mcp = read_json(f"{surface}/.mcp.json")
            self.assertEqual(set(mcp.keys()), {"mcpServers"}, msg=f"{surface}/.mcp.json must only declare mcpServers")
            servers = mcp.get("mcpServers")
            self.assertIsInstance(servers, dict, msg=f"{surface}/.mcp.json must wrap servers under mcpServers")
            self.assertIn("plate-core", servers)
            self.assertEqual(servers["plate-core"].get("command"), "plate-mcp")

    def test_grok_marketplace_manifest_and_index_exist(self):
        # Grok uses .grok-plugin/ at repo root (distinct from Copilot's .github/plugin/)
        grok_manifest = read_json(".grok-plugin/marketplace.json")
        self.assertEqual(grok_manifest["name"], "plate-marketplace")
        self.assertEqual(len(grok_manifest["plugins"]), 1)
        entry = grok_manifest["plugins"][0]
        self.assertEqual(entry["name"], "plate-core")
        self.assertEqual(entry["version"], __version__)
        # source is local dict pointing at the committed payload (same as used by e2e structure tests)
        self.assertEqual(entry["source"]["type"], "local")
        self.assertEqual(entry["source"]["path"], "./.plugin")

        # plugin-index.json is the committed catalog for rich Marketplace tab previews (TUI)
        index = read_json(".grok-plugin/plugin-index.json")
        self.assertEqual(index["version"], 1)
        self.assertIn("plate-core", index["plugins"])
        components = index["plugins"]["plate-core"]["components"]
        self.assertIn("agents", components)
        self.assertIn("mcpServers", components)
        self.assertTrue(any(a["name"] == "plate" for a in components["agents"]))
        self.assertTrue(any(m["name"] == "plate-core" for m in components["mcpServers"]))
        self.assertIn("skills", components)
        self.assertGreaterEqual(len(components["skills"]), 18)

    def test_grok_generator_check_passes(self):
        # The generator must be deterministic and match the committed index.
        # This is the packaging gate (run via `python3 scripts/generate-grok-plugin-index.py --check`).
        import subprocess
        from pathlib import Path
        repo_root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            ["python3", str(repo_root / "scripts" / "generate-grok-plugin-index.py"), "--check"],
            capture_output=True,
            text=True,
            cwd=repo_root,
        )
        self.assertEqual(result.returncode, 0, msg=f"generator --check failed:\n{result.stderr}\n{result.stdout}")
        self.assertIn("Plugin index OK", result.stdout)

    def test_readme_documents_prelaunch_marketplace_install_flow(self):
        readme = read_text("README.md")

        self.assertIn("copilot plugin marketplace add akasper/plate", readme)
        self.assertIn("copilot plugin install plate-core@plate-marketplace", readme)
        self.assertIn("grok plugin marketplace add akasper/plate", readme)
        self.assertIn("grok plugin install plate-core@plate-marketplace --trust", readme)
        # Prefer pinned install after v0.8.0 (#998); unpinned form also acceptable.
        self.assertIn("pip install", readme)
        self.assertTrue(
            "plate-core==0.8.0" in readme or "pip install plate-core" in readme,
            msg="README must document plate-core pip install (pinned or unpinned)",
        )
        self.assertIn("There is no separate GitHub-run submission process for Copilot CLI or Grok Build marketplaces", readme)
        self.assertIn("Marketplace release checklist", readme)
        self.assertIn("#380 and #381", readme)
        self.assertIn("docs/bootstrap/marketplace-install-checklist.md", readme)

    def test_maintainer_marketplace_checklist_doc(self):
        """#379: dedicated maintainer checklist links human Tasks and both host surfaces."""
        checklist = read_text("docs/bootstrap/marketplace-install-checklist.md")
        self.assertIn("#378", checklist)
        self.assertIn("#379", checklist)
        self.assertIn("#380", checklist)
        self.assertIn("#381", checklist)
        self.assertIn(".github/plugin/marketplace.json", checklist)
        self.assertIn(".grok-plugin/marketplace.json", checklist)
        self.assertIn("source: \"plugin\"", checklist)
        self.assertIn("pip install", checklist)
        self.assertTrue(
            "plate-core==0.8.0" in checklist or "pip install plate-core" in checklist,
            msg="checklist must document plate-core pip install (pinned or unpinned)",
        )
        self.assertIn("do not agent-complete", checklist)
        self.assertIn("Never auto-publish", checklist)

    def test_ci_uses_repo_marketplace_as_prelaunch_surface(self):
        workflow = read_text(".github/workflows/ci.yml")

        self.assertIn("Plugin install smoke test (pre-launch marketplace surface)", workflow)
        # Note: the conditional if (only on main push) was removed in #375 to run the
        # supported marketplace smoke unconditionally on all PRs (prevents hangs from
        # deprecated direct installs and provides early validation).
        self.assertIn("copilot plugin marketplace add akasper/plate", workflow)
        self.assertIn("copilot plugin install plate-core@plate-marketplace", workflow)
        self.assertIn("copilot plugin marketplace remove plate-marketplace --force", workflow)
        # Grok packaging is validated via the committed generator + --check (no public binary
        # download yet; the generator + unit tests cover the .grok-plugin/ surface for #570).
        self.assertIn("Grok marketplace packaging check (generator + committed index)", workflow)
        self.assertIn("generate-grok-plugin-index.py --check", workflow)
        self.assertIn("generate-plugin-skills.py --check", workflow)


if __name__ == "__main__":
    unittest.main()
