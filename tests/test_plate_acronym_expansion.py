"""Guard against retired PLATE acronym expansions in shipped surfaces (#1157)."""

from __future__ import annotations

import unittest
from pathlib import Path

from plate_core.branding import LEGACY_PLATE_ACRONYM_EXPANSIONS, PLATE_ACRONYM_EXPANSION

REPO_ROOT = Path(__file__).resolve().parents[1]

# Roots scanned recursively for text files (excluding historical release dirs).
SCAN_ROOTS = (
    "README.md",
    "AGENTS.md",
    "SPEC.md",
    "pyproject.toml",
    "docs",
    "plugin",
    ".plugin",
    ".grok-plugin",
    ".agentic/process.yml",
    "src/plate_core",
)

# tests/ is not scanned; branding.py holds LEGACY_* constants for this guard only.

SKIP_DIR_NAMES = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    "node_modules",
    ".venv",
    "venv",
}

# Historical release notes and changelogs describe the past; do not rewrite.
SKIP_PATH_PARTS = (
    ".agentic/releases/",
    "CHANGELOG",
    "COSTS.md",
)


def _should_scan(path: Path) -> bool:
    rel = path.relative_to(REPO_ROOT).as_posix()
    if rel.endswith("plate_core/branding.py"):
        return False
    for part in SKIP_PATH_PARTS:
        if part in rel:
            return False
    if path.suffix.lower() not in {
        "",
        ".md",
        ".yml",
        ".yaml",
        ".json",
        ".toml",
        ".py",
        ".txt",
        ".ps1",
        ".sh",
    }:
        return False
    return True


def _iter_shipped_files() -> list[Path]:
    found: list[Path] = []
    for root_name in SCAN_ROOTS:
        root = REPO_ROOT / root_name
        if not root.exists():
            continue
        if root.is_file():
            if _should_scan(root):
                found.append(root)
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if any(part in SKIP_DIR_NAMES for part in path.parts):
                continue
            if _should_scan(path):
                found.append(path)
    return sorted(set(found))


class PlateAcronymExpansionTests(unittest.TestCase):
    def test_canonical_expansion_documented(self):
        self.assertIn("Product Lifecycle", PLATE_ACRONYM_EXPANSION)
        self.assertIn("Automation Toolkit", PLATE_ACRONYM_EXPANSION)

    def test_legacy_expansions_absent_from_shipped_files(self):
        offenders: list[str] = []
        for path in _iter_shipped_files():
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            rel = path.relative_to(REPO_ROOT).as_posix()
            for legacy in LEGACY_PLATE_ACRONYM_EXPANSIONS:
                if legacy in text:
                    offenders.append(f"{rel}: contains `{legacy}`")
        self.assertEqual(
            offenders,
            [],
            "Retired PLATE acronym expansions found:\n" + "\n".join(offenders),
        )

    def test_readme_uses_canonical_expansion(self):
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn(PLATE_ACRONYM_EXPANSION, readme)

    def test_process_yml_uses_canonical_name(self):
        import yaml

        for rel in (".agentic/process.yml", "src/plate_core/template_payload/.agentic/process.yml"):
            data = yaml.safe_load((REPO_ROOT / rel).read_text(encoding="utf-8"))
            self.assertEqual(data["process"]["name"], PLATE_ACRONYM_EXPANSION)


if __name__ == "__main__":
    unittest.main()
