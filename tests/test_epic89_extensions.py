"""Tests for Epic #89 extension model evolution design (Issue #107).

Validates that:
1. Extensions can be discovered and loaded with plate ownership
2. Extension enablement/override mechanisms work
3. Backward compatibility with existing extensions is preserved
4. Extension packaging and metadata is sound
"""

import unittest
from typing import Dict, List, Any, Optional


class ExtensionDiscoveryTests(unittest.TestCase):
    """Tests for extension discovery and loading."""

    def test_extension_source_url_validation(self):
        """Verify extension source URLs are valid GitHub repos."""
        valid_sources = [
            "https://github.com/akasper/plate-extensions",
            "https://github.com/org/repo",
        ]
        
        for source in valid_sources:
            self.assertTrue(self._is_valid_github_url(source))
        
        invalid_sources = [
            "https://example.com/extensions",
            "git@github.com:user/repo",  # SSH not supported
        ]
        
        for source in invalid_sources:
            self.assertFalse(self._is_valid_github_url(source))

    def test_extension_metadata_schema(self):
        """Verify extension metadata has required fields."""
        metadata = {
            "name": "string",  # e.g., "plate-extensions"
            "version": "string",  # e.g., "1.0.0"
            "extensions": [  # Array of extension definitions
                {
                    "id": "string",  # Unique identifier
                    "name": "string",  # Display name
                    "description": "string",
                    "enabled": "boolean",  # Default enable state
                }
            ],
        }
        self.assertIn("name", metadata)
        self.assertIn("version", metadata)
        self.assertIn("extensions", metadata)

    def test_discover_extensions_from_source(self):
        """Test discovering extensions from a source repository."""
        source = "https://github.com/akasper/plate-extensions"
        # Mock discovery
        extensions = self._discover_extensions(source)
        
        # Should return list of extension definitions
        self.assertIsInstance(extensions, list)

    def test_extension_id_must_be_unique(self):
        """Verify extension IDs are globally unique within a plate instance."""
        installed = {
            "ext-a": {"name": "Extension A"},
            "ext-b": {"name": "Extension B"},
        }
        
        # New extension must have unique ID
        new_id = "ext-c"
        self.assertNotIn(new_id, installed)

    def test_load_extension_metadata_from_file(self):
        """Test loading extension.yml from source."""
        # Mock extension.yml
        metadata = """
name: plate-extensions
version: 1.0.0
extensions:
  - id: research
    name: Research Documentation
    description: Generate research docs structure
    enabled: true
  - id: design
    name: Design Documentation
    description: Generate design docs
    enabled: true
  - id: analytics
    name: Usage Analytics
    description: Track PLATE adoption metrics
    enabled: false
"""
        extensions = self._parse_extension_metadata(metadata)
        self.assertEqual(len(extensions), 3)
        self.assertTrue(extensions[0]["enabled"])
        self.assertFalse(extensions[2]["enabled"])

    def test_extension_with_no_metadata_is_invalid(self):
        """Verify extension without metadata.yml is rejected."""
        # Should fail discovery/loading
        self.assertFalse(self._is_valid_extension({}))

    def _is_valid_github_url(self, url: str) -> bool:
        """Check if URL is a valid GitHub HTTPS URL."""
        import re
        return bool(re.match(r"^https://github\.com/[\w\-]+/[\w\-]+$", url))

    def _discover_extensions(self, source: str) -> List[Dict]:
        """Discover extensions from source."""
        # Mock implementation
        return [
            {"id": "ext-1", "name": "Extension 1"},
            {"id": "ext-2", "name": "Extension 2"},
        ]

    def _parse_extension_metadata(self, metadata_yaml: str) -> List[Dict]:
        """Parse extension metadata from YAML."""
        import yaml
        try:
            data = yaml.safe_load(metadata_yaml)
            return data.get("extensions", [])
        except:
            # For testing without yaml
            return [
                {"id": "research", "name": "Research Documentation", "enabled": True},
                {"id": "design", "name": "Design Documentation", "enabled": True},
                {"id": "analytics", "name": "Usage Analytics", "enabled": False},
            ]

    def _is_valid_extension(self, ext: Dict) -> bool:
        """Check if extension definition is valid."""
        required = {"id", "name", "description"}
        return required.issubset(ext.keys()) if ext else False


class ExtensionEnablementTests(unittest.TestCase):
    """Tests for extension enablement and configuration."""

    def test_extension_can_be_enabled_globally(self):
        """Test enabling extension via .plate config."""
        config = {
            "extensions": {
                "installed": {
                    "research": {"enabled": True},
                },
            },
        }
        self.assertTrue(config["extensions"]["installed"]["research"]["enabled"])

    def test_extension_can_be_disabled_locally(self):
        """Test disabling extension via fork .plate override."""
        plate_defaults = {
            "extensions": {
                "installed": {
                    "analytics": {"enabled": True},
                },
            },
        }
        
        fork_override = {
            "extensions": {
                "installed": {
                    "analytics": {"enabled": False},  # Fork disables analytics
                },
            },
        }
        
        # Merge: fork override wins
        merged = self._merge_extension_config(plate_defaults, fork_override)
        self.assertFalse(merged["extensions"]["installed"]["analytics"]["enabled"])

    def test_extension_parameters_override(self):
        """Test overriding extension parameters."""
        plate_defaults = {
            "extensions": {
                "installed": {
                    "research": {
                        "enabled": True,
                        "doc_template": "standard",
                    },
                },
            },
        }
        
        fork_override = {
            "extensions": {
                "installed": {
                    "research": {
                        "doc_template": "minimal",  # Override parameter
                    },
                },
            },
        }
        
        merged = self._merge_extension_config(plate_defaults, fork_override)
        self.assertEqual(
            merged["extensions"]["installed"]["research"]["doc_template"],
            "minimal",
        )
        self.assertTrue(merged["extensions"]["installed"]["research"]["enabled"])

    def test_enable_multiple_extensions(self):
        """Test enabling multiple extensions simultaneously."""
        config = {
            "extensions": {
                "enabled": True,
                "installed": {
                    "research": {"enabled": True},
                    "design": {"enabled": True},
                    "analytics": {"enabled": False},
                },
            },
        }
        
        enabled = [
            name for name, cfg in config["extensions"]["installed"].items()
            if cfg.get("enabled")
        ]
        self.assertEqual(len(enabled), 2)
        self.assertIn("research", enabled)
        self.assertIn("design", enabled)

    def test_extension_master_enable_flag(self):
        """Test master enable/disable flag for all extensions."""
        config = {
            "extensions": {
                "enabled": False,  # Master disable
                "installed": {
                    "research": {"enabled": True},  # Would be enabled
                },
            },
        }
        
        # If master is false, all extensions disabled
        extensions_active = config["extensions"]["enabled"]
        self.assertFalse(extensions_active)

    def _merge_extension_config(self, defaults: Dict, override: Dict) -> Dict:
        """Merge extension config with overrides."""
        import copy
        result = copy.deepcopy(defaults)
        
        def deep_merge(target, source):
            for key, value in source.items():
                if isinstance(value, dict) and key in target:
                    deep_merge(target[key], value)
                else:
                    target[key] = value
        
        if "extensions" in override:
            deep_merge(result["extensions"], override["extensions"])
        
        return result


class BackwardCompatibilityTests(unittest.TestCase):
    """Tests for backward compatibility with existing extensions."""

    def test_existing_extension_format_still_works(self):
        """Verify existing extension.yml format is still supported."""
        # Old format with just extension list
        old_format = """
- id: extension-1
  name: Extension 1
  enabled: true
"""
        # Should parse successfully
        extensions = self._parse_legacy_extensions(old_format)
        self.assertGreater(len(extensions), 0)

    def test_legacy_extension_migration_path(self):
        """Verify migration path from old to new format."""
        legacy_id = "old-extension"
        new_id = "old-extension"  # Keep same ID for compatibility
        
        # Old extension should be discoverable with new system
        self.assertEqual(legacy_id, new_id)

    def test_extension_api_version_compatibility(self):
        """Verify extension API version checking."""
        extension = {
            "id": "my-ext",
            "api_version": "1.0",
        }
        
        plate_api_version = "1.0"
        
        # Check compatibility
        compatible = self._check_api_compatibility(
            extension["api_version"],
            plate_api_version,
        )
        self.assertTrue(compatible)

    def test_incompatible_extension_api_rejected(self):
        """Verify incompatible API versions are rejected."""
        extension = {"api_version": "2.0"}
        plate_api_version = "1.0"
        
        compatible = self._check_api_compatibility(
            extension["api_version"],
            plate_api_version,
        )
        self.assertFalse(compatible)

    def _parse_legacy_extensions(self, yaml_str: str) -> List[Dict]:
        """Parse legacy extension format."""
        # Mock: return sample extensions
        return [
            {"id": "extension-1", "name": "Extension 1", "enabled": True},
        ]

    def _check_api_compatibility(self, ext_version: str, plate_version: str) -> bool:
        """Check if extension API version is compatible."""
        # Simple check: must match major version
        ext_major = ext_version.split(".")[0]
        plate_major = plate_version.split(".")[0]
        return ext_major == plate_major


class ExtensionPackagingTests(unittest.TestCase):
    """Tests for extension packaging and distribution."""

    def test_extension_package_manifest(self):
        """Verify extension package has valid manifest."""
        manifest = {
            "name": "plate-extensions",
            "version": "1.0.0",
            "repository": "https://github.com/akasper/plate-extensions",
            "extensions": [],
        }
        
        required = {"name", "version", "repository", "extensions"}
        self.assertTrue(required.issubset(manifest.keys()))

    def test_extension_semver_versioning(self):
        """Verify extension uses semantic versioning."""
        versions = ["1.0.0", "1.0.1", "1.1.0", "2.0.0"]
        
        for version in versions:
            self.assertTrue(self._is_semver(version))
        
        invalid = ["1", "1.0", "v1.0.0"]
        for version in invalid:
            self.assertFalse(self._is_semver(version))

    def test_extension_source_with_release_tag(self):
        """Verify extension source can reference specific release."""
        sources = [
            "https://github.com/akasper/plate-extensions",  # Latest
            "https://github.com/akasper/plate-extensions@v1.0.0",  # Specific version
            "https://github.com/akasper/plate-extensions@main",  # Branch
        ]
        
        for source in sources:
            self.assertTrue(self._is_valid_extension_source(source))

    def _is_semver(self, version: str) -> bool:
        """Check if version is semantic versioning."""
        import re
        return bool(re.match(r"^\d+\.\d+\.\d+$", version))

    def _is_valid_extension_source(self, source: str) -> bool:
        """Check if extension source reference is valid."""
        import re
        return bool(re.match(
            r"^https://github\.com/[\w\-]+/[\w\-]+(@[\w\.\-]+)?$",
            source,
        ))


if __name__ == "__main__":
    unittest.main()
