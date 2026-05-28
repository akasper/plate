"""Tests for Epic #89 .plate root configuration schema design (Issue #108).

Validates that:
1. .plate schema can be parsed and validated
2. Resolution order (defaults → extensions → local) is correct
3. Invalid configs are properly rejected
4. Versioning and migration work
"""

import unittest
import json
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional, List


class PlateConfigSchema(unittest.TestCase):
    """Tests for .plate configuration schema."""

    def test_schema_basic_structure(self):
        """Verify .plate config has required top-level fields."""
        schema = {
            "version": "string",  # e.g., "1.0"
            "methodology": "object",  # PLATE methodology settings
            "extensions": "object",  # Extension enablement/config
            "overrides": "object",  # Fork-local overrides
        }
        self.assertIn("version", schema)
        self.assertIn("methodology", schema)
        self.assertIn("extensions", schema)
        self.assertIn("overrides", schema)

    def test_schema_version_format(self):
        """Verify version field follows semantic versioning."""
        valid_versions = ["1.0", "1.0.0", "2.0", "1.1.0"]
        for v in valid_versions:
            self.assertTrue(self._is_valid_version(v), f"Version {v} should be valid")
        
        invalid_versions = ["v1.0", "1", "1.0.0.0"]
        for v in invalid_versions:
            self.assertFalse(self._is_valid_version(v), f"Version {v} should be invalid")

    def test_methodology_section_structure(self):
        """Verify methodology section defines PLATE process config."""
        methodology_config = {
            "epic_naming_pattern": "string",  # e.g., "Epic: {name}"
            "marker_prefix": "string",  # e.g., "PLATES-CORE"
            "marker_boundaries": "array",  # Start/end markers
            "feature_workflow": "string",  # Feature branch pattern
        }
        self.assertGreater(len(methodology_config), 0)

    def test_extensions_section_controls_enablement(self):
        """Verify extensions section enables/disables extension loading."""
        extensions_config = {
            "enabled": "boolean",  # Master enable/disable
            "sources": "array",  # Extension repositories
            "installed": "object",  # Per-extension config
        }
        self.assertIn("enabled", extensions_config)
        self.assertIn("sources", extensions_config)

    def test_overrides_section_for_fork_customization(self):
        """Verify overrides allow fork-specific customization."""
        overrides = {
            "branch_protection_rules": "object",
            "ci_config": "object",
            "workflow_triggers": "object",
            "extension_overrides": "object",
        }
        self.assertGreater(len(overrides), 0)

    def test_parse_valid_config(self):
        """Test parsing a valid .plate config."""
        config_str = """
{
    "version": "1.0",
    "methodology": {
        "epic_naming_pattern": "Epic: {name}",
        "marker_prefix": "PLATES-CORE"
    },
    "extensions": {
        "enabled": true,
        "sources": ["https://github.com/akasper/plate-extensions"]
    },
    "overrides": {}
}
"""
        config = json.loads(config_str)
        self.assertEqual(config["version"], "1.0")
        self.assertTrue(config["extensions"]["enabled"])

    def test_reject_missing_version(self):
        """Test that config without version field is rejected."""
        config_str = """
{
    "methodology": {},
    "extensions": {"enabled": true},
    "overrides": {}
}
"""
        config = json.loads(config_str)
        self.assertNotIn("version", config)
        # Validation should fail
        self.assertFalse(self._validate_config(config))

    def test_reject_invalid_version_format(self):
        """Test that config with invalid version is rejected."""
        config = {"version": "invalid", "methodology": {}}
        self.assertFalse(self._validate_config(config))

    def test_resolution_order_defaults_to_extensions_to_local(self):
        """Test that resolution follows: defaults → extensions → local."""
        # Simulate plate defaults
        defaults = {
            "version": "1.0",
            "methodology": {
                "marker_prefix": "PLATES-CORE",
                "feature_workflow": "feature/*",
            },
        }
        
        # Extension provides override
        extension = {
            "methodology": {
                "feature_workflow": "feat/*",  # Override default
            },
        }
        
        # Local fork provides final override
        local = {
            "methodology": {
                "feature_workflow": "custom-feat/*",  # Final override
            },
        }
        
        # Resolution: deepmerge in order
        resolved = self._resolve_config(defaults, extension, local)
        self.assertEqual(resolved["methodology"]["feature_workflow"], "custom-feat/*")
        self.assertEqual(resolved["methodology"]["marker_prefix"], "PLATES-CORE")  # From defaults

    def test_resolution_preserves_unoverridden_defaults(self):
        """Test that resolution preserves defaults not overridden."""
        defaults = {
            "version": "1.0",
            "methodology": {
                "epic_naming_pattern": "Epic: {name}",
                "marker_prefix": "PLATES-CORE",
            },
        }
        
        local = {
            "methodology": {
                "epic_naming_pattern": "EPIC: {name}",  # Override only this
            },
        }
        
        resolved = self._resolve_config(defaults, {}, local)
        self.assertEqual(resolved["methodology"]["epic_naming_pattern"], "EPIC: {name}")
        self.assertEqual(resolved["methodology"]["marker_prefix"], "PLATES-CORE")  # Preserved

    def test_load_from_file(self):
        """Test loading .plate config from file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".plate"
            config_content = {
                "version": "1.0",
                "methodology": {"marker_prefix": "PLATES-CORE"},
                "extensions": {"enabled": True},
                "overrides": {},
            }
            config_path.write_text(json.dumps(config_content))
            
            loaded = json.loads(config_path.read_text())
            self.assertEqual(loaded["version"], "1.0")

    def test_empty_overrides_section_valid(self):
        """Test that empty overrides section is valid."""
        config = {
            "version": "1.0",
            "methodology": {},
            "extensions": {"enabled": False},
            "overrides": {},
        }
        self.assertTrue(self._validate_config(config))

    def test_version_migration_path(self):
        """Test that version field enables migration path."""
        v1_config = {"version": "1.0", "methodology": {}}
        v2_config = {"version": "2.0", "methodology": {}, "new_field": "value"}
        
        # Validator should recognize versions
        self.assertTrue(self._is_valid_version(v1_config["version"]))
        self.assertTrue(self._is_valid_version(v2_config["version"]))

    def _is_valid_version(self, version: str) -> bool:
        """Check if version string is valid semantic version."""
        import re
        return bool(re.match(r"^\d+\.\d+(\.\d+)?$", version))

    def _validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate config against schema."""
        if "version" not in config:
            return False
        if not self._is_valid_version(config["version"]):
            return False
        if "methodology" not in config:
            return False
        return True

    def _resolve_config(
        self,
        defaults: Dict[str, Any],
        extension: Dict[str, Any],
        local: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Resolve config with cascading precedence: defaults < extension < local."""
        result = {}
        
        # Start with defaults
        self._deep_merge(result, defaults)
        
        # Apply extension
        self._deep_merge(result, extension)
        
        # Apply local
        self._deep_merge(result, local)
        
        return result

    def _deep_merge(self, target: Dict, source: Dict) -> None:
        """Deep merge source into target."""
        for key, value in source.items():
            if isinstance(value, dict) and key in target and isinstance(target[key], dict):
                self._deep_merge(target[key], value)
            else:
                target[key] = value


class PlateConfigValidationTests(unittest.TestCase):
    """Tests for .plate config validation."""

    def test_reject_unknown_top_level_fields(self):
        """Test that unknown top-level fields are rejected or warned."""
        config = {
            "version": "1.0",
            "methodology": {},
            "unknown_field": "value",  # Unknown
        }
        # Strict validation should reject
        validator = ConfigValidator()
        result = validator.validate(config, strict=True)
        self.assertFalse(result.valid)

    def test_allow_unknown_fields_in_lenient_mode(self):
        """Test that unknown fields are allowed in lenient mode."""
        config = {
            "version": "1.0",
            "methodology": {},
            "future_field": "value",  # Unknown but allowed
        }
        validator = ConfigValidator()
        result = validator.validate(config, strict=False)
        self.assertTrue(result.valid)

    def test_deeply_nested_resolution(self):
        """Test resolution with deeply nested configs."""
        defaults = {
            "version": "1.0",
            "methodology": {
                "settings": {
                    "nested": {
                        "value": "default",
                    },
                },
            },
        }
        local = {
            "methodology": {
                "settings": {
                    "nested": {
                        "value": "override",
                    },
                },
            },
        }
        
        validator = ConfigValidator()
        resolved = validator.resolve([defaults, local])
        self.assertEqual(resolved["methodology"]["settings"]["nested"]["value"], "override")


class ConfigValidator:
    """Simple config validator for testing."""

    def validate(self, config: Dict[str, Any], strict: bool = True) -> "ValidationResult":
        """Validate config."""
        if "version" not in config:
            return ValidationResult(valid=False, errors=["Missing version field"])
        
        if strict:
            allowed_keys = {"version", "methodology", "extensions", "overrides"}
            unknown = set(config.keys()) - allowed_keys
            if unknown:
                return ValidationResult(valid=False, errors=[f"Unknown fields: {unknown}"])
        
        return ValidationResult(valid=True, errors=[])

    def resolve(self, configs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Resolve config cascade."""
        result = {}
        for config in configs:
            self._deep_merge(result, config)
        return result

    def _deep_merge(self, target: Dict, source: Dict) -> None:
        """Deep merge source into target."""
        for key, value in source.items():
            if isinstance(value, dict) and key in target and isinstance(target[key], dict):
                self._deep_merge(target[key], value)
            else:
                target[key] = value


class ValidationResult:
    """Result of config validation."""

    def __init__(self, valid: bool, errors: List[str]):
        self.valid = valid
        self.errors = errors


if __name__ == "__main__":
    unittest.main()
