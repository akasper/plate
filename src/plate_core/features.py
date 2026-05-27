"""Optional PLATE feature detection for repository state."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .github_client import GhApiError, GhClient
from .health import resolve_repo


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
        ("playwright-e2e", "playwright.config.ts"),
    ]
    detected = [FeatureFlag(name=name, enabled=_path_exists(gh, target, path), evidence=path) for name, path in checks]
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
    """Check if repo has Playwright E2E setup (local file check)."""
    checks = [
        (repo_path / "playwright.config.ts").exists(),
        (repo_path / "tests" / "e2e").is_dir(),
        "playwright" in _get_package_json_deps(repo_path) or "@playwright/test" in _get_package_json_deps(repo_path),
    ]
    return all(checks)
