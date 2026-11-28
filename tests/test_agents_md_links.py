"""Regression: on-demand AGENTS.md links must resolve in-tree (#1479)."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PAYLOAD_ROOT = REPO_ROOT / "src" / "plate_core" / "template_payload"

# Relative markdown links in AGENTS.md (excluding http(s), mailto, anchors-only).
_LINK_RE = re.compile(r"\]\(([^)#]+)\)")


def _collect_relative_links(agents_path: Path) -> list[tuple[int, str]]:
    lines: list[tuple[int, str]] = []
    text = agents_path.read_text(encoding="utf-8")
    for line_no, line in enumerate(text.splitlines(), start=1):
        for match in _LINK_RE.finditer(line):
            target = match.group(1).strip()
            if not target or target.startswith(("http://", "https://", "mailto:")):
                continue
            if target.startswith("#"):
                continue
            lines.append((line_no, target))
    return lines


def _assert_links_resolve(agents_path: Path, repo_root: Path) -> None:
    missing: list[str] = []
    for line_no, target in _collect_relative_links(agents_path):
        resolved = (repo_root / target).resolve()
        try:
            resolved.relative_to(repo_root.resolve())
        except ValueError:
            missing.append(f"{agents_path}:{line_no}: {target} escapes repo root")
            continue
        if not resolved.is_file():
            missing.append(f"{agents_path}:{line_no}: {target} -> {resolved} (missing)")
    if missing:
        self_fail = "\n".join(missing)
        raise AssertionError(f"Broken AGENTS.md links under {repo_root}:\n{self_fail}")


class AgentsMdLinkResolutionTest(unittest.TestCase):
    def test_root_agents_md_on_demand_links(self) -> None:
        agents = REPO_ROOT / "AGENTS.md"
        self.assertTrue(agents.is_file(), "AGENTS.md must exist at repository root")
        _assert_links_resolve(agents, REPO_ROOT)

    def test_template_payload_agents_md_on_demand_links(self) -> None:
        agents = PAYLOAD_ROOT / "AGENTS.md"
        self.assertTrue(agents.is_file(), "template payload AGENTS.md must exist")
        _assert_links_resolve(agents, PAYLOAD_ROOT)

    def test_root_agents_md_does_not_use_stale_agents_prefix(self) -> None:
        text = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertNotIn("](agents/", text, "Use docs/agents/ for on-demand rule pages")

    def test_payload_agents_md_does_not_use_stale_agents_prefix(self) -> None:
        text = (PAYLOAD_ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertNotIn("](agents/", text, "Use docs/agents/ for on-demand rule pages")


if __name__ == "__main__":
    unittest.main()