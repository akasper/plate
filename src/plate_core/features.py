"""Optional PLATE feature detection for repository state."""

from __future__ import annotations

import base64
import binascii
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .github_client import GhApiError, GhClient
from .health import resolve_repo


# Playwright E2E config file candidates (support .ts/.js/.mjs/.cjs per common usage)
PLAYWRIGHT_CONFIG_CANDIDATES: list[str] = [
    "playwright.config.ts",
    "playwright.config.js",
    "playwright.config.mjs",
    "playwright.config.cjs",
]


@dataclass
class FeatureFlag:
    name: str
    enabled: bool
    evidence: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class FeatureReport:
    repo: str
    features: list[FeatureFlag]

    def to_dict(self) -> dict:
        return {"repo": self.repo, "features": [x.to_dict() for x in self.features]}


def _path_exists(client: GhClient, repo: str, path: str) -> bool:
    try:
        client.api(f"repos/{repo}/contents/{path}")
        return True
    except GhApiError:
        return False


def _has_playwright_config_gh(client: GhClient, repo: str) -> tuple[bool, str]:
    """Check for any playwright.config.* via GitHub API. Returns (enabled, evidence)."""
    for name in PLAYWRIGHT_CONFIG_CANDIDATES:
        if _path_exists(client, repo, name):
            return True, name
    # Fallback per issue #64 heuristic: tests/e2e + playwright dependency.
    if _path_exists(client, repo, "tests/e2e") and _has_playwright_dep_gh(client, repo):
        return True, "tests/e2e/ + package.json playwright dependency"
    return False, "playwright.config.* or (tests/e2e/ + package.json playwright dependency)"


def _has_playwright_dep_gh(client: GhClient, repo: str) -> bool:
    """Check for playwright/@playwright/test dependency in package.json via GitHub API."""
    try:
        package_json = client.api(f"repos/{repo}/contents/package.json")
    except GhApiError:
        return False
    if not isinstance(package_json, dict):
        return False
    content = package_json.get("content")
    if not isinstance(content, str):
        return False
    try:
        decoded = base64.b64decode(content).decode("utf-8")
        data = json.loads(decoded)
    except (ValueError, TypeError, UnicodeDecodeError, binascii.Error):
        return False
    deps: set[str] = set()
    for section in ("dependencies", "devDependencies", "peerDependencies"):
        section_deps = data.get(section, {})
        if isinstance(section_deps, dict):
            deps.update(section_deps.keys())
    return bool(deps & {"playwright", "@playwright/test"})


def get_features(repo: str | None = None, client: GhClient | None = None) -> FeatureReport:
    gh = client or GhClient()
    target = resolve_repo(repo)
    checks = [
        ("autonomous-mode", ".github/AUTONOMOUS_MODE"),
        ("platform-monitor-workflow", ".github/workflows/platform-monitor.yml"),
        ("copilot-plugin-root", ".plugin/plugin.json"),
        ("copilot-plugin-source", "plugin/plugin.json"),
        ("mcp-manifest-root", ".plugin/.mcp.json"),
        ("mcp-manifest-source", "plugin/.mcp.json"),
        ("baseline-agents-catalog", "src/plate_core/data/baseline_catalog.yml"),
        ("current-md", "CURRENT.md"),
    ]
    detected = [FeatureFlag(name=name, enabled=_path_exists(gh, target, path), evidence=path) for name, path in checks]

    # Playwright uses flexible heuristic per issue #64 (config.* + optional dir/dep signals)
    pw_enabled, pw_evidence = _has_playwright_config_gh(gh, target)
    detected.append(FeatureFlag(name="playwright-e2e", enabled=pw_enabled, evidence=pw_evidence))

    return FeatureReport(repo=target, features=detected)


def _get_package_json_deps(repo_path: Path) -> set[str]:
    """Extract package names from package.json dependencies."""
    package_json = repo_path / "package.json"
    if not package_json.exists():
        return set()
    try:
        with open(package_json, encoding='utf-8-sig') as f:
            data = json.load(f)
        deps = set()
        for section in ["dependencies", "devDependencies", "peerDependencies"]:
            deps.update(data.get(section, {}).keys())
        return deps
    except Exception:
        return set()


def detect_playwright_e2e_local(repo_path: Path) -> bool:
    """Check if repo has Playwright E2E setup (local file check).

    Per issue #64 heuristic: playwright.config.* presence (any variant) OR
    (tests/e2e/ directory + playwright package dep).
    """
    has_config = any((repo_path / name).exists() for name in PLAYWRIGHT_CONFIG_CANDIDATES)
    has_e2e_dir = (repo_path / "tests" / "e2e").is_dir()
    deps = _get_package_json_deps(repo_path)
    has_dep = bool(deps & {"playwright", "@playwright/test"})
    return has_config or (has_e2e_dir and has_dep)
