"""Hybrid / non-code project support for the Q&A + autonomous lifecycle (#650).

Extends PLATE beyond traditional software Features/Bugs to:
- Marketing sites, docs, content repos
- Design systems, infra-as-code
- Hybrid products (code + content + marketing)

First slice: project kinds, artifact types, validation strategies, planning
templates, and repo-signal detection. Downstream loops can consume these
contracts without assuming unit tests alone.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HYBRID_DIR = Path(".agentic/hybrid")
PROFILE_FILE = "project_profile.json"
MARKER_BEGIN = "<!-- PLATE-HYBRID:BEGIN -->"
MARKER_END = "<!-- PLATE-HYBRID:END -->"

# Canonical project kinds
PROJECT_KINDS: dict[str, dict[str, Any]] = {
    "software": {
        "label": "Software product",
        "description": "Traditional code Features/Bugs with unit/integration tests",
        "default_artifact_types": ["code", "tests", "api", "cli"],
        "validation": ["unit_tests", "integration_tests", "typecheck", "lint"],
        "deploy_targets": ["pypi", "container", "gh_release"],
        "issue_emphasis": ["Feature", "Bug", "Epic"],
    },
    "docs": {
        "label": "Documentation / wiki",
        "description": "Docs sites, handbooks, methodology prose",
        "default_artifact_types": ["markdown", "wiki", "diagram"],
        "validation": ["link_check", "markdown_lint", "spellcheck", "structure_review"],
        "deploy_targets": ["pages", "docs_site", "wiki"],
        "issue_emphasis": ["Documentation", "Feature", "Question"],
    },
    "content": {
        "label": "Content / editorial",
        "description": "Long-form content, blog, knowledge base",
        "default_artifact_types": ["article", "markdown", "media"],
        "validation": ["content_lint", "link_check", "editorial_review", "seo_check"],
        "deploy_targets": ["cms", "static_site", "newsletter"],
        "issue_emphasis": ["Feature", "Task", "Question"],
    },
    "marketing": {
        "label": "Marketing site",
        "description": "Landing pages, campaigns, claims surfaces",
        "default_artifact_types": ["page", "copy", "media", "cta"],
        "validation": [
            "link_check",
            "visual_regression",
            "claims_review",
            "a11y_scan",
            "lighthouse",
        ],
        "deploy_targets": ["marketing_site", "cdn", "cms"],
        "issue_emphasis": ["Feature", "Design", "Task"],
    },
    "design_system": {
        "label": "Design system",
        "description": "Tokens, components, visual language",
        "default_artifact_types": ["component", "token", "story", "figma"],
        "validation": [
            "visual_regression",
            "a11y_scan",
            "storybook_build",
            "design_contract",
        ],
        "deploy_targets": ["storybook", "npm_package", "figma_library"],
        "issue_emphasis": ["Design", "Feature", "Bug"],
    },
    "infra": {
        "label": "Infrastructure as code",
        "description": "Terraform/Pulumi/K8s/CI platform config",
        "default_artifact_types": ["iac", "pipeline", "policy"],
        "validation": ["plan_diff", "policy_check", "dry_run_apply", "secret_scan"],
        "deploy_targets": ["cloud", "cluster", "ci"],
        "issue_emphasis": ["Feature", "Bug", "Task"],
    },
    "hybrid": {
        "label": "Hybrid product",
        "description": "Code + content + marketing (or multi-surface product)",
        "default_artifact_types": ["code", "markdown", "page", "media", "tests"],
        "validation": [
            "unit_tests",
            "link_check",
            "content_lint",
            "visual_regression",
            "claims_review",
        ],
        "deploy_targets": ["app", "docs_site", "marketing_site", "gh_release"],
        "issue_emphasis": ["Feature", "Epic", "Design", "Documentation"],
    },
}

ARTIFACT_TYPES: dict[str, dict[str, Any]] = {
    "code": {"label": "Source code", "extensions": [".py", ".ts", ".go", ".rs", ".java"]},
    "tests": {"label": "Automated tests", "extensions": [".py", ".ts", ".spec.ts"]},
    "api": {"label": "API surface", "extensions": [".yaml", ".json", ".proto"]},
    "cli": {"label": "CLI entrypoint", "extensions": []},
    "markdown": {"label": "Markdown prose", "extensions": [".md", ".mdx"]},
    "wiki": {"label": "Wiki page", "extensions": [".md"]},
    "diagram": {"label": "Architecture diagram", "extensions": [".mmd", ".svg", ".png"]},
    "article": {"label": "Editorial article", "extensions": [".md", ".mdx"]},
    "media": {"label": "GIF/video/image media", "extensions": [".gif", ".mp4", ".png", ".jpg"]},
    "page": {"label": "Web page / route", "extensions": [".tsx", ".html", ".vue"]},
    "copy": {"label": "Marketing copy", "extensions": [".md", ".json"]},
    "cta": {"label": "Call-to-action asset", "extensions": []},
    "component": {"label": "UI component", "extensions": [".tsx", ".vue", ".svelte"]},
    "token": {"label": "Design token", "extensions": [".json", ".css", ".ts"]},
    "story": {"label": "Storybook story", "extensions": [".stories.tsx", ".mdx"]},
    "figma": {"label": "Figma artifact ref", "extensions": []},
    "iac": {"label": "Infrastructure as code", "extensions": [".tf", ".yml", ".yaml"]},
    "pipeline": {"label": "CI/CD pipeline", "extensions": [".yml", ".yaml"]},
    "policy": {"label": "Policy / guardrail", "extensions": [".rego", ".yml"]},
}

# Validation strategy catalog (id → how agents should treat it)
VALIDATION_STRATEGIES: dict[str, dict[str, Any]] = {
    "unit_tests": {
        "label": "Unit tests",
        "command_hint": "pytest / npm test",
        "suitable_for": ["software", "hybrid", "design_system"],
    },
    "integration_tests": {
        "label": "Integration tests",
        "command_hint": "pytest -m integration / e2e suite",
        "suitable_for": ["software", "hybrid"],
    },
    "typecheck": {
        "label": "Typecheck",
        "command_hint": "mypy / tsc --noEmit",
        "suitable_for": ["software", "hybrid", "design_system"],
    },
    "lint": {
        "label": "Lint",
        "command_hint": "ruff / eslint",
        "suitable_for": ["software", "hybrid", "docs", "content"],
    },
    "link_check": {
        "label": "Link checker",
        "command_hint": "lychee / markdown-link-check",
        "suitable_for": ["docs", "content", "marketing", "hybrid"],
    },
    "markdown_lint": {
        "label": "Markdown lint",
        "command_hint": "markdownlint",
        "suitable_for": ["docs", "content", "marketing"],
    },
    "spellcheck": {
        "label": "Spellcheck",
        "command_hint": "cspell / codespell",
        "suitable_for": ["docs", "content", "marketing"],
    },
    "structure_review": {
        "label": "Doc structure review",
        "command_hint": "TOC/nav consistency check",
        "suitable_for": ["docs"],
    },
    "content_lint": {
        "label": "Content lint / style guide",
        "command_hint": "vale / custom style rules",
        "suitable_for": ["content", "marketing", "hybrid"],
    },
    "editorial_review": {
        "label": "Editorial human review",
        "command_hint": "checkpoint: editor approve",
        "suitable_for": ["content", "marketing"],
        "requires_human": True,
    },
    "seo_check": {
        "label": "SEO checklist",
        "command_hint": "meta/title/heading scan",
        "suitable_for": ["content", "marketing"],
    },
    "visual_regression": {
        "label": "Visual regression",
        "command_hint": "Playwright screenshots / Chromatic",
        "suitable_for": ["marketing", "design_system", "hybrid"],
    },
    "claims_review": {
        "label": "Marketing claims review",
        "command_hint": "checkpoint: claims truthful vs product",
        "suitable_for": ["marketing", "hybrid"],
        "requires_human": True,
    },
    "a11y_scan": {
        "label": "Accessibility scan",
        "command_hint": "axe / pa11y",
        "suitable_for": ["marketing", "design_system", "software", "hybrid"],
    },
    "lighthouse": {
        "label": "Lighthouse perf/a11y",
        "command_hint": "lighthouse CI",
        "suitable_for": ["marketing", "software"],
    },
    "design_contract": {
        "label": "Design contract (#646)",
        "command_hint": "plate_design_contract_validate",
        "suitable_for": ["design_system", "software", "hybrid", "marketing"],
    },
    "storybook_build": {
        "label": "Storybook build",
        "command_hint": "npm run build-storybook",
        "suitable_for": ["design_system"],
    },
    "plan_diff": {
        "label": "IaC plan/diff",
        "command_hint": "terraform plan / pulumi preview",
        "suitable_for": ["infra"],
    },
    "policy_check": {
        "label": "Policy as code",
        "command_hint": "opa / conftest",
        "suitable_for": ["infra"],
    },
    "dry_run_apply": {
        "label": "Dry-run apply",
        "command_hint": "apply --dry-run",
        "suitable_for": ["infra"],
        "requires_human": True,
    },
    "secret_scan": {
        "label": "Secret scan",
        "command_hint": "gitleaks / trufflehog",
        "suitable_for": ["infra", "software", "hybrid"],
    },
}


@dataclass
class ProjectProfile:
    kind: str
    label: str = ""
    description: str = ""
    artifact_types: list[str] = field(default_factory=list)
    validation: list[str] = field(default_factory=list)
    deploy_targets: list[str] = field(default_factory=list)
    issue_emphasis: list[str] = field(default_factory=list)
    detected_signals: list[str] = field(default_factory=list)
    confidence: float = 0.0
    updated_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def render_hybrid_marker(payload: dict[str, Any]) -> str:
    return f"{MARKER_BEGIN}\n{json.dumps(payload, indent=2)}\n{MARKER_END}\n"


def list_project_kinds() -> list[dict[str, Any]]:
    return [
        {"id": kid, **{k: v for k, v in meta.items()}}
        for kid, meta in PROJECT_KINDS.items()
    ]


def list_artifact_types() -> list[dict[str, Any]]:
    return [{"id": aid, **meta} for aid, meta in ARTIFACT_TYPES.items()]


def list_validation_strategies(*, kind: str | None = None) -> list[dict[str, Any]]:
    rows = []
    for vid, meta in VALIDATION_STRATEGIES.items():
        if kind and kind not in (meta.get("suitable_for") or []):
            continue
        rows.append({"id": vid, **meta})
    return rows


def get_kind_contract(kind: str) -> dict[str, Any] | None:
    meta = PROJECT_KINDS.get(kind)
    if not meta:
        return None
    return {
        "kind": kind,
        **meta,
        "validation_details": [
            {"id": v, **VALIDATION_STRATEGIES[v]}
            for v in meta.get("validation") or []
            if v in VALIDATION_STRATEGIES
        ],
        "artifact_details": [
            {"id": a, **ARTIFACT_TYPES[a]}
            for a in meta.get("default_artifact_types") or []
            if a in ARTIFACT_TYPES
        ],
    }


def detect_project_kind(repo_root: Path | str | None = None) -> dict[str, Any]:
    """Heuristic project-kind detection from filesystem signals."""
    root = Path(repo_root or ".")
    scores: dict[str, float] = {k: 0.0 for k in PROJECT_KINDS}
    signals: list[str] = []

    def bump(kind: str, amount: float, signal: str) -> None:
        scores[kind] = scores.get(kind, 0.0) + amount
        if signal not in signals:
            signals.append(signal)

    # Software signals
    for name in ("pyproject.toml", "setup.py", "package.json", "Cargo.toml", "go.mod"):
        if (root / name).exists():
            bump("software", 2.0, f"found:{name}")
    if (root / "src").is_dir():
        bump("software", 1.0, "dir:src")
    if (root / "tests").is_dir():
        bump("software", 1.0, "dir:tests")

    # Docs
    for name in ("docs", "wiki", "documentation"):
        if (root / name).is_dir():
            bump("docs", 2.0, f"dir:{name}")
    if (root / "mkdocs.yml").exists() or (root / "docusaurus.config.js").exists():
        bump("docs", 2.5, "docs_tooling")

    # Marketing / content
    for name in ("marketing", "content", "blog", "campaigns"):
        if (root / name).is_dir():
            bump("marketing" if name in ("marketing", "campaigns") else "content", 2.0, f"dir:{name}")
    if (root / "astro.config.mjs").exists() or (root / "hugo.toml").exists():
        bump("marketing", 1.5, "static_site_tooling")
        bump("content", 1.0, "static_site_tooling")

    # Design system
    if (root / ".storybook").is_dir() or (root / "packages" / "tokens").is_dir():
        bump("design_system", 2.5, "storybook_or_tokens")
    if any((root / p).exists() for p in ("tokens.json", "design-tokens.json")):
        bump("design_system", 2.0, "design_tokens_file")

    # Infra
    for name in ("terraform", "infra", "deploy", "k8s", "helm"):
        if (root / name).is_dir():
            bump("infra", 2.0, f"dir:{name}")
    if list(root.glob("*.tf"))[:1]:
        bump("infra", 2.5, "tf_files")
    if (root / ".github" / "workflows").is_dir():
        bump("infra", 0.5, "github_workflows")
        bump("software", 0.5, "github_workflows")

    # Hybrid if multiple strong surfaces
    strong = [k for k, s in scores.items() if k != "hybrid" and s >= 2.0]
    if len(strong) >= 2:
        bump("hybrid", 3.0 + 0.5 * len(strong), f"multi_surface:{','.join(sorted(strong))}")

    # Prefer highest score; default software
    best = max(scores.items(), key=lambda kv: kv[1])
    kind = best[0] if best[1] > 0 else "software"
    if best[1] <= 0:
        signals.append("default:software")
    total = sum(scores.values()) or 1.0
    confidence = min(1.0, best[1] / max(3.0, total * 0.5))

    contract = get_kind_contract(kind) or {}
    profile = ProjectProfile(
        kind=kind,
        label=str(contract.get("label") or kind),
        description=str(contract.get("description") or ""),
        artifact_types=list(contract.get("default_artifact_types") or []),
        validation=list(contract.get("validation") or []),
        deploy_targets=list(contract.get("deploy_targets") or []),
        issue_emphasis=list(contract.get("issue_emphasis") or []),
        detected_signals=signals,
        confidence=round(confidence, 3),
        updated_at=_now(),
        metadata={"scores": scores},
    )
    return {
        "ok": True,
        "profile": profile.to_dict(),
        "scores": scores,
        "contract": contract,
        "marker": render_hybrid_marker({"kind": kind, "confidence": profile.confidence}),
    }


def set_project_kind(
    kind: str,
    *,
    base_dir: Path | None = None,
    extra_artifacts: list[str] | None = None,
    extra_validation: list[str] | None = None,
    note: str = "",
) -> dict[str, Any]:
    """Persist an explicit project kind override."""
    if kind not in PROJECT_KINDS:
        return {"ok": False, "error": f"unknown kind: {kind}", "known": list(PROJECT_KINDS)}
    contract = get_kind_contract(kind) or {}
    arts = list(contract.get("default_artifact_types") or [])
    vals = list(contract.get("validation") or [])
    for a in extra_artifacts or []:
        if a not in arts:
            arts.append(a)
    for v in extra_validation or []:
        if v not in vals:
            vals.append(v)
    profile = ProjectProfile(
        kind=kind,
        label=str(contract.get("label") or kind),
        description=str(contract.get("description") or ""),
        artifact_types=arts,
        validation=vals,
        deploy_targets=list(contract.get("deploy_targets") or []),
        issue_emphasis=list(contract.get("issue_emphasis") or []),
        detected_signals=["explicit_set"],
        confidence=1.0,
        updated_at=_now(),
        metadata={"note": note, "source": "explicit"},
    )
    path = (base_dir or HYBRID_DIR) / PROFILE_FILE
    if base_dir and base_dir.name == PROFILE_FILE:
        path = base_dir
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": 1, "profile": profile.to_dict()}
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return {"ok": True, "profile": profile.to_dict(), "path": str(path)}


def load_project_profile(
    *,
    base_dir: Path | None = None,
    repo_root: Path | str | None = None,
    detect_if_missing: bool = True,
) -> dict[str, Any]:
    path = (base_dir or HYBRID_DIR) / PROFILE_FILE
    if base_dir and base_dir.name == PROFILE_FILE:
        path = base_dir
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            prof = data.get("profile") if isinstance(data, dict) else None
            if isinstance(prof, dict):
                return {"ok": True, "profile": prof, "source": "persisted", "path": str(path)}
        except (OSError, json.JSONDecodeError):
            pass
    if detect_if_missing:
        det = detect_project_kind(repo_root)
        return {
            "ok": True,
            "profile": det.get("profile"),
            "source": "detected",
            "scores": det.get("scores"),
            "contract": det.get("contract"),
        }
    return {"ok": False, "error": "no profile"}


def planning_template_for_kind(kind: str) -> dict[str, Any]:
    """Q&A planning template tuned to project kind (feeds #628/#630)."""
    contract = get_kind_contract(kind)
    if not contract:
        return {"ok": False, "error": f"unknown kind: {kind}"}
    questions = [
        {
            "id": "outcome",
            "question": f"What user-visible outcome should this {contract['label']} change deliver?",
            "options_hint": ["ship", "clarify", "defer"],
        },
        {
            "id": "artifacts",
            "question": "Which artifact types are in scope?",
            "options": [
                {"id": a, "label": ARTIFACT_TYPES.get(a, {}).get("label", a)}
                for a in contract.get("default_artifact_types") or []
            ],
        },
        {
            "id": "validation",
            "question": "Which validation strategies must pass before merge?",
            "options": [
                {"id": v["id"], "label": v.get("label") or v["id"]}
                for v in contract.get("validation_details") or []
            ],
        },
        {
            "id": "deploy",
            "question": "Where does this change deploy?",
            "options": [
                {"id": d, "label": d} for d in contract.get("deploy_targets") or []
            ],
        },
        {
            "id": "human_gates",
            "question": "Any human-only gates (claims, editorial, production apply)?",
            "options": [
                {"id": "none", "label": "None"},
                {"id": "claims", "label": "Claims review"},
                {"id": "editorial", "label": "Editorial review"},
                {"id": "prod_apply", "label": "Production apply"},
            ],
        },
    ]
    ac_templates = [
        f"Artifact types declared and match project kind `{kind}`",
        "Validation strategy list attached to Feature (not unit-tests-only by default)",
        "Deploy target named; dry-run path documented when high risk",
        "If marketing/content: claims or editorial human gate identified",
    ]
    return {
        "ok": True,
        "kind": kind,
        "label": contract.get("label"),
        "questions": questions,
        "acceptance_criteria_templates": ac_templates,
        "issue_types": contract.get("issue_emphasis") or [],
        "ask_user_question": {
            "question": f"Plan next change as {contract.get('label')}?",
            "options": [
                {
                    "id": "start",
                    "label": "Start kind-aware planning",
                    "description": f"Use hybrid template for {kind}",
                },
                {
                    "id": "switch",
                    "label": "Switch project kind",
                    "description": "plate_hybrid_set_kind",
                },
            ],
        },
    }


def feature_validation_plan(
    kind: str,
    *,
    feature_title: str = "",
    artifact_types: list[str] | None = None,
) -> dict[str, Any]:
    """Build a Feature-level validation plan for non-code or hybrid work."""
    contract = get_kind_contract(kind)
    if not contract:
        return {"ok": False, "error": f"unknown kind: {kind}"}
    arts = artifact_types or list(contract.get("default_artifact_types") or [])
    steps = []
    for v in contract.get("validation_details") or []:
        steps.append(
            {
                "id": v["id"],
                "label": v.get("label"),
                "command_hint": v.get("command_hint"),
                "requires_human": bool(v.get("requires_human")),
                "status": "pending",
            }
        )
    return {
        "ok": True,
        "kind": kind,
        "feature_title": feature_title,
        "artifact_types": arts,
        "steps": steps,
        "tdd_note": (
            "Prefer failing checks first (broken link fixture, failing axe rule, "
            "red visual snapshot) before implementation — same as unit TDD."
        ),
        "marker": render_hybrid_marker(
            {"kind": kind, "feature": feature_title, "n_steps": len(steps)}
        ),
    }


def hybrid_feed_items(
    *,
    base_dir: Path | None = None,
    repo_root: Path | str | None = None,
    limit: int = 4,
) -> list[dict[str, Any]]:
    """Feed signals when hybrid profile is unset or multi-surface detected."""
    loaded = load_project_profile(
        base_dir=base_dir, repo_root=repo_root, detect_if_missing=True
    )
    prof = loaded.get("profile") or {}
    items: list[dict[str, Any]] = []
    source = loaded.get("source")
    kind = prof.get("kind") or "software"
    if source == "detected" and kind != "software":
        items.append(
            {
                "id": f"hybrid-detect-{kind}",
                "item_type": "hybrid_profile",
                "title": f"Detected project kind: {prof.get('label') or kind}",
                "rank": 18,
                "impact": "medium",
                "badges": ["hybrid", kind, "detected"],
                "source": "hybrid",
                "reason": "Non-software or hybrid signals (#650)",
                "prompt_segment": (
                    f"Confirm project kind `{kind}` via plate_hybrid_set_kind or "
                    f"plate_hybrid_detect. Use kind-aware planning templates."
                ),
                "ask_user_question": {
                    "question": f"Use detected project kind '{prof.get('label') or kind}'?",
                    "options": [
                        {
                            "id": "confirm",
                            "label": f"Confirm {kind}",
                            "description": f"plate_hybrid_set_kind {kind}",
                        },
                        {
                            "id": "software",
                            "label": "Keep software default",
                            "description": "plate_hybrid_set_kind software",
                        },
                        {
                            "id": "list",
                            "label": "List kinds",
                            "description": "plate_hybrid_list_kinds",
                        },
                    ],
                },
                "profile": prof,
            }
        )
    # Do not spam the endless feed for software-default repos; only surface
    # when non-software / multi-surface signals fire (handled above).
    return items[:limit]
