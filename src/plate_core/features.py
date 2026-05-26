"""Optional PLATE feature detection for repository state."""

from __future__ import annotations

from dataclasses import asdict, dataclass

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
        ("current-md", "CURRENT.md"),
    ]
    detected = [FeatureFlag(name=name, enabled=_path_exists(gh, target, path), evidence=path) for name, path in checks]
    return FeatureReport(repo=target, features=detected)
