#!/usr/bin/env python3
"""Offline compound PLATE flow proofs for the Playwright e2e harness (#927 / #364).

No network, no real GitHub, no destructive apply. Prints a single JSON object:
  { "ok": true, "claims": [ ... ], "results": { ... } }

Claims cover:
  1. babysit→merge eligibility gates (block then unblock)
  2. release cut dry-run + finalize/sync plan dry surfaces
  3. Q&A contemplate → artifact mutation PR-only draft plan
"""

from __future__ import annotations

import json
import sys
import tempfile
from io import StringIO
from pathlib import Path
from typing import Any

# Prefer in-tree package when spawned from Playwright with PYTHONPATH=src.
REPO_ROOT = Path(__file__).resolve().parents[3]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _claim(claims: list[str], name: str) -> None:
    claims.append(name)


def prove_babysit_merge_gates(claims: list[str], results: dict[str, Any]) -> None:
    from plate_core.pr_babysit import evaluate_babysit_gates

    blocked = evaluate_babysit_gates(
        {
            "merge_state": "BEHIND",
            "unresolved_review_threads": 2,
            "actionable_agent_threads": 1,
            "review_decision": "",
            "ci_failing": True,
            "ci_pending": False,
            "failing_checks": 1,
        }
    )
    assert blocked["blocked"] is True, blocked
    _claim(claims, "babysit_gates_block_when_behind_threads_or_ci_fail")

    clean = evaluate_babysit_gates(
        {
            "merge_state": "CLEAN",
            "unresolved_review_threads": 0,
            "actionable_agent_threads": 0,
            "review_decision": "APPROVED",
            "ci_failing": False,
            "ci_pending": False,
            "failing_checks": 0,
            "pending_checks": 0,
        }
    )
    assert clean["blocked"] is False, clean
    _claim(claims, "babysit_gates_unblock_when_clean_approved_ci_green")
    results["babysit"] = {"blocked": blocked, "clean": clean}


def _seed_version_files(repo_root: Path, version: str = "0.1.0") -> None:
    """Mirror tests/test_release._seed_version_files for offline cut dry-run."""
    (repo_root / "src" / "plate_core").mkdir(parents=True, exist_ok=True)
    (repo_root / "plugin").mkdir(parents=True, exist_ok=True)
    (repo_root / ".plugin").mkdir(parents=True, exist_ok=True)
    (repo_root / ".github" / "plugin").mkdir(parents=True, exist_ok=True)
    (repo_root / ".grok-plugin").mkdir(parents=True, exist_ok=True)
    (repo_root / "src" / "plate_core" / "__init__.py").write_text(
        f'"""plate_core runtime package."""\n\n__version__ = "{version}"\n',
        encoding="utf-8",
    )
    (repo_root / "pyproject.toml").write_text(
        "\n".join(
            [
                "[project]",
                'name = "plate-core"',
                f'version = "{version}"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    plugin_manifest = {
        "name": "plate-core",
        "version": version,
        "repository": "https://github.com/akasper/plate",
    }
    (repo_root / "plugin" / "plugin.json").write_text(
        json.dumps(plugin_manifest), encoding="utf-8"
    )
    (repo_root / ".plugin" / "plugin.json").write_text(
        json.dumps(plugin_manifest), encoding="utf-8"
    )
    (repo_root / ".github" / "plugin" / "marketplace.json").write_text(
        json.dumps(
            {
                "name": "plate-marketplace",
                "metadata": {"version": version},
                "plugins": [
                    {"name": "plate-core", "source": "plugin", "version": version}
                ],
            }
        ),
        encoding="utf-8",
    )
    (repo_root / ".grok-plugin" / "marketplace.json").write_text(
        json.dumps(
            {
                "name": "grok-marketplace",
                "plugins": [
                    {"name": "plate-core", "source": "plugin", "version": version}
                ],
            }
        ),
        encoding="utf-8",
    )


def prove_release_cut_and_finalize_dry(claims: list[str], results: dict[str, Any]) -> None:
    from plate_core.release import cut_release, plan_gh_plate_sync

    with tempfile.TemporaryDirectory() as tmp:
        # cut_release treats releases_dir as the releases tree and walks up to
        # find_repo_root (pyproject + src/plate_core). Seed both on one root.
        root = Path(tmp)
        _seed_version_files(root, "0.1.0")
        releases = root / ".agentic" / "releases"
        unreleased = releases / "unreleased"
        unreleased.mkdir(parents=True)
        prior = releases / "v0.1.0"
        prior.mkdir()
        (prior / "release.json").write_text(
            json.dumps({"version": "0.1.0", "entries": []}),
            encoding="utf-8",
        )
        frag = {
            "slug": "compound-e2e-demo",
            "change_type": "feature",
            "surface": "tests/e2e",
            "summary": "Compound e2e fixture fragment for dry cut.",
            "migration_impact": "none",
            "agent_notes": "fixture only",
            "breaking": False,
            "links": ["#927"],
        }
        (unreleased / "compound-e2e-demo.json").write_text(
            json.dumps(frag, indent=2),
            encoding="utf-8",
        )

        buf = StringIO()
        old = sys.stdout
        try:
            sys.stdout = buf
            code = cut_release(
                version=None,
                releases_dir=releases,
                version_type="patch",
                dry_run=True,
            )
        finally:
            sys.stdout = old
        out = buf.getvalue()
        assert code == 0, out
        assert "[DRY RUN]" in out, out
        assert "Would create" in out or "release.json" in out, out
        # Dry-run must not materialize the versioned directory.
        assert not (releases / "v0.1.1").exists(), "dry_run wrote versioned dir"
        _claim(claims, "release_cut_dry_run_aggregates_fragments_without_write")

        plan = plan_gh_plate_sync("0.1.1")
        assert isinstance(plan, dict), plan
        assert plan.get("ok") is True, plan
        assert plan.get("tag") == "v0.1.1", plan
        assert isinstance(plan.get("steps"), list) and plan["steps"], plan
        _claim(claims, "release_finalize_sync_plan_is_structured_dry_surface")
        results["release"] = {
            "cut_exit": code,
            "cut_stdout_has_dry_run": "[DRY RUN]" in out,
            "sync_plan_keys": sorted(plan.keys()),
        }


def prove_contemplate_mutation_plan(claims: list[str], results: dict[str, Any]) -> None:
    from plate_core.contemplation import ContemplationEngine

    class _FakeGh:
        def __init__(self) -> None:
            self.posted: list[tuple[str, str, dict | None]] = []

        def api(self, endpoint: str, method: str = "GET", fields: dict | None = None):
            if method == "GET" and endpoint.endswith("/issues/326"):
                return {
                    "number": 326,
                    "title": "Process Q",
                    "body": "## Answer signal\nDocument without checklist.\n",
                }
            if method == "GET" and endpoint.endswith("/comments"):
                return []
            if method == "POST":
                self.posted.append((endpoint, (fields or {}).get("body", ""), fields))
                if endpoint.endswith("/issues"):
                    return {
                        "number": 901,
                        "html_url": "https://example.invalid/issues/901",
                    }
                return {"html_url": "https://example.invalid/comments/1"}
            raise AssertionError(f"unexpected {method} {endpoint}")

    client = _FakeGh()
    answer = (
        "Please update AGENTS.md Question loop and change process so "
        "process updates only land via PR. Also add a skill in .agentic/skills.yml."
    )
    result = ContemplationEngine(client).contemplate(
        question_number=326,
        answer_text=answer,
        repo="owner/repo",
        answered_by="e2e-driver",
    )
    intents = result.get("mutation_intents") or []
    paths = {i.get("path") for i in intents}
    assert "AGENTS.md" in paths, result
    assert result.get("mutation_pr_draft"), result
    assert "release" in (result.get("mutation_pr_draft") or "").lower()
    assert any(i.get("mutation_plan") for i in result.get("created_issues") or []), result
    _claim(claims, "contemplate_detects_process_mutation_intents_pr_only")
    _claim(claims, "contemplate_opens_feature_mutation_plan_with_release_base_draft")
    results["contemplate"] = {
        "paths": sorted(paths),
        "created_types": [i.get("type") for i in result.get("created_issues") or []],
        "has_pr_draft": bool(result.get("mutation_pr_draft")),
    }


def main() -> int:
    claims: list[str] = []
    results: dict[str, Any] = {}
    try:
        prove_babysit_merge_gates(claims, results)
        prove_release_cut_and_finalize_dry(claims, results)
        prove_contemplate_mutation_plan(claims, results)
    except Exception as exc:  # noqa: BLE001 — surface to Playwright
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": f"{type(exc).__name__}: {exc}",
                    "claims": claims,
                    "results": results,
                }
            ),
            flush=True,
        )
        return 1

    print(
        json.dumps(
            {
                "ok": True,
                "claims": claims,
                "results": results,
                "proves": "#927/#364 compound Playwright offline chain",
            }
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
