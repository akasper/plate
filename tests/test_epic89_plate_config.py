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
        self._deep_merge(result, defaults)
        self._deep_merge(result, extension)
        self._deep_merge(result, local)
        return result

    def _deep_merge(self, target: Dict[str, Any], source: Dict[str, Any]) -> None:
        """Deep merge source into target (for legacy sketch tests)."""
        for key, value in source.items():
            if isinstance(value, dict) and key in target and isinstance(target[key], dict):
                self._deep_merge(target[key], value)
            else:
                target[key] = value


# --- Real runtime integration tests for Issue #129 implementation ---
from plate_core.plate_config import (
    CURRENT_CONFIG_VERSION,
    load_plate_config,
    PlateConfig,
    PlateConfigError,
    validate_plate_config,
    DEFAULT_CONFIG,
    apply_plate_config_upgrade,
    get_plate_config_report,
    init_plate_config,
    upgrade_plate_config_dict,
)


class PlateConfigRuntimeTests(unittest.TestCase):
    """Tests exercising the actual plate_config module (Issue #129)."""

    def test_load_defaults_when_no_file(self):
        cfg = load_plate_config(Path("/tmp/nonexistent-plate-root-xyz"))
        self.assertEqual(cfg.version, CURRENT_CONFIG_VERSION)
        self.assertEqual(cfg.methodology.get("marker_prefix"), "PLATES-CORE")

    def test_load_and_validate_local_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".plate").write_text(json.dumps({
                "version": "1.0",
                "methodology": {"marker_prefix": "CUSTOM"},
                "extensions": {"enabled": False},
                "overrides": {"ci": "fast"},
            }))
            cfg = load_plate_config(root)
            self.assertEqual(cfg.methodology["marker_prefix"], "CUSTOM")
            self.assertFalse(cfg.extensions["enabled"])

    def test_validation_rejects_missing_version(self):
        bad = {"methodology": {}, "extensions": {}, "overrides": {}}
        with self.assertRaises(PlateConfigError):
            validate_plate_config(bad)

    def test_validation_accepts_valid(self):
        good = {"version": "1.0", "methodology": {}, "extensions": {}, "overrides": {}}
        validate_plate_config(good)  # no raise

    def test_module_exports_defaults(self):
        self.assertIn("version", DEFAULT_CONFIG)
        self.assertIn("marker_prefix", DEFAULT_CONFIG["methodology"])

    def test_get_plate_config_report_returns_defaults_when_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = get_plate_config_report(Path(tmp))
            self.assertFalse(report.present)
            self.assertTrue(report.valid)
            self.assertEqual(report.source, "defaults")
            self.assertEqual(report.config["version"], CURRENT_CONFIG_VERSION)

    def test_init_plate_config_creates_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = init_plate_config(Path(tmp))
            self.assertTrue((Path(tmp) / ".plate").exists())
            self.assertTrue(report.present)
            self.assertTrue(report.valid)
            self.assertEqual(report.source, "local_file")
            self.assertEqual(report.resolved_version, CURRENT_CONFIG_VERSION)

    def test_init_plate_config_rejects_existing_file_without_force(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".plate").write_text(json.dumps({"version": "1.0"}))
            with self.assertRaises(PlateConfigError):
                init_plate_config(root)

    def test_deeply_nested_resolution(self):
        """Test resolution with deeply nested configs."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".plate").write_text(
                json.dumps(
                    {
                        "version": "1.1",
                        "methodology": {
                            "settings": {
                                "nested": {
                                    "value": "override",
                                }
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            resolved = load_plate_config(root).to_dict()
            self.assertEqual(resolved["methodology"]["settings"]["nested"]["value"], "override")

    def test_enabled_builtin_extension_contributes_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".plate").write_text(
                json.dumps(
                    {
                        "version": "1.2",
                        "extensions": {"enabled": True, "installed": {"release-track-management": True}},
                        "autonomy": {"enabled": False, "risk_tolerance": "off", "token_budget": {"daily": 50000, "per_cycle": 8000, "action": "throttle"}, "cost_ceiling_usd": 10.0, "schedules_enabled": False, "loop": {"default_sleep_seconds": 300, "max_cycles": None}},
                        "overrides": {},
                    }
                ),
                encoding="utf-8",
            )
            cfg = load_plate_config(root)
            self.assertEqual(cfg.release["triggers"], ["require-release-track-label"])
            report = get_plate_config_report(root)
            self.assertEqual(report.extension_providers["release-track-management"], "builtin:release-ceremony")
            self.assertEqual(report.extension_path_providers["release.triggers"], "builtin:release-ceremony")

    def test_autonomy_validation_rejects_invalid_payloads(self):
        """Covers autonomy schema validation added in this PR (addresses review: exercise valid/invalid autonomy cases)."""
        # Valid minimal
        validate_plate_config({"version": "1.2", "autonomy": {"enabled": False, "risk_tolerance": "off"}}, strict=True)
        # Invalid risk
        with self.assertRaises(PlateConfigError):
            validate_plate_config({"version": "1.2", "autonomy": {"risk_tolerance": "banana"}}, strict=True)
        # Bool for numeric
        with self.assertRaises(PlateConfigError):
            validate_plate_config({"version": "1.2", "autonomy": {"token_budget": {"daily": True}}}, strict=True)
        # Unknown key under autonomy
        with self.assertRaises(PlateConfigError):
            validate_plate_config({"version": "1.2", "autonomy": {"foo": 1}}, strict=True)
        # Unknown under token_budget
        with self.assertRaises(PlateConfigError):
            validate_plate_config({"version": "1.2", "autonomy": {"token_budget": {"foo": 1}}}, strict=True)
        # #634 per_action is a first-class optional token_budget key
        validate_plate_config(
            {
                "version": "1.2",
                "autonomy": {
                    "token_budget": {
                        "daily": 50000,
                        "per_cycle": 8000,
                        "per_action": 2000,
                        "action": "throttle",
                    }
                },
            },
            strict=True,
        )

    def test_local_overrides_win_over_extension_contribution(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".plate").write_text(
                json.dumps(
                    {
                        "version": "1.1",
                        "extensions": {
                            "enabled": True,
                            "installed": {
                                "specialist-agents": {
                                    "enabled": True,
                                    "config": {
                                        "overrides": {
                                            "delegation_defaults": {
                                                "featured_agent_ids": ["security-auditor", "performance-engineer"]
                                            }
                                        }
                                    },
                                }
                            },
                        },
                        "overrides": {
                            "delegation_defaults": {
                                "featured_agent_ids": ["security-auditor"]
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            cfg = load_plate_config(root)
            self.assertEqual(cfg.overrides["delegation_defaults"]["featured_agent_ids"], ["security-auditor"])

    def test_master_extension_flag_disables_extension_contributions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".plate").write_text(
                json.dumps(
                    {
                        "version": "1.1",
                        "extensions": {"enabled": False, "installed": {"release-track-management": True}},
                        "overrides": {},
                    }
                ),
                encoding="utf-8",
            )
            cfg = load_plate_config(root)
            self.assertEqual(cfg.release["triggers"], [])

    def test_upgrade_plate_config_dict_migrates_legacy_shape(self):
        upgraded, guidance, previous_version = upgrade_plate_config_dict(
            {
                "version": "1.0",
                "methodology": {"marker_prefix": "PLATES-CORE"},
                "extensions": {"enabled": True, "installed": {"release-track-management": True}},
                "overrides": {},
            }
        )
        self.assertEqual(previous_version, "1.0")
        self.assertEqual(upgraded["version"], CURRENT_CONFIG_VERSION)
        self.assertIn("release", upgraded)
        self.assertEqual(upgraded["extensions"]["installed"]["release-track-management"]["enabled"], True)
        self.assertTrue(guidance)

    def test_apply_plate_config_upgrade_writes_file_when_requested(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / ".plate"
            path.write_text(
                json.dumps(
                    {
                        "version": "1.0",
                        "methodology": {"marker_prefix": "PLATES-CORE"},
                        "extensions": {"enabled": True},
                        "overrides": {},
                    }
                ),
                encoding="utf-8",
            )
            report = apply_plate_config_upgrade(root, apply=True)
            self.assertTrue(report.changed)
            self.assertTrue(report.applied)
            upgraded = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(upgraded["version"], CURRENT_CONFIG_VERSION)


class ConfigValidator:
    """Simple config validator for testing."""

    def validate(self, config: Dict[str, Any], strict: bool = True) -> "ValidationResult":
        """Validate config."""
        if "version" not in config:
            return ValidationResult(valid=False, errors=["Missing version field"])
        
        if strict:
            allowed_keys = {"version", "methodology", "extensions", "overrides", "release"}
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


class TestAutonomySchemaDefaultsAndMigration(unittest.TestCase):
    """Tests for v1.2 autonomy addition, defaults, compat (no key in .plate), and migration (Epic #470 / #474 skeleton + config)."""

    def test_default_autonomy_present_and_valid(self):
        # DEFAULT now includes autonomy with 'medium'/'enabled' as the intended new behavior for the autonomy engine feature (Epic #470 / this PR); conservative 'off' applies on migration when no section or explicit off in .plate
        self.assertIn("autonomy", DEFAULT_CONFIG)
        auto = DEFAULT_CONFIG["autonomy"]
        self.assertEqual(auto.get("risk_tolerance"), "medium")
        self.assertTrue(auto.get("enabled"))
        validate_plate_config({"version": "1.2", "autonomy": auto}, strict=True)

        # Note: PR #504 labeled with exactly one type label "Bug" (+ risk:low, area:agent) to satisfy .github/workflows/labels.yml PR type label rule.

    def test_load_without_autonomy_key_resolves_via_default(self):
        # A .plate lacking 'autonomy' (like pre-this-change) should still load and resolve to having autonomy via DEFAULT (explicit in root .plate now)
        # Use a temp minimal .plate without the key
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".plate").write_text(json.dumps({
                "version": "1.1",
                "release": {"triggers": []}
            }))
            cfg = load_plate_config(root)
            self.assertTrue(hasattr(cfg, "autonomy") or "autonomy" in getattr(cfg, "to_dict", lambda: {})())
            # resolved should have autonomy section (deep merge)
            d = cfg.to_dict() if hasattr(cfg, "to_dict") else {}
            # plate_config dataclass or dict-like
            autonomy = getattr(cfg, "autonomy", None) or d.get("autonomy", {})
            self.assertIsInstance(autonomy, dict)
            self.assertIn("risk_tolerance", autonomy)

    def test_migrate_1_1_to_1_2_adds_autonomy(self):
        raw = {"version": "1.1", "release": {"triggers": []}}
        upgraded = upgrade_plate_config_dict(raw)
        # Depending on return shape (tuple or dict in some paths), ensure autonomy appears
        if isinstance(upgraded, tuple):
            data = upgraded[0]
        else:
            data = upgraded
        self.assertIn("autonomy", data)
        self.assertEqual(data.get("version"), "1.2")

if __name__ == "__main__":
    unittest.main()
