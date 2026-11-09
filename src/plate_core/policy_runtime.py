"""Trusted policy runtime verification for CI (#1449).

Policy modules must be loaded from default-branch vendored ``src/plate_core``
(see ``.agentic/policy-runtime.json``). PR-head code must not be treated as
authoritative for merge enforcement.
"""

from __future__ import annotations

import importlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path

DEFAULT_MANIFEST = Path(".agentic/policy-runtime.json")

REQUIRED_POLICY_MODULES: tuple[str, ...] = (
    "plate_core.pr_integration_base_gate",
    "plate_core.pr_main_source_gate",
    "plate_core.branch_policy",
    "plate_core.issue_context",
)


@dataclass(frozen=True)
class PolicyRuntimeManifest:
    schema: int
    required_modules: tuple[str, ...]
    plate_core_max_known_wheel: str | None
    trusted_execution_note: str


def load_manifest(path: Path | None = None) -> PolicyRuntimeManifest:
    manifest_path = path or DEFAULT_MANIFEST
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    wheel = raw.get("plate_core_wheel") or {}
    return PolicyRuntimeManifest(
        schema=int(raw.get("schema", 1)),
        required_modules=tuple(wheel.get("required_modules") or REQUIRED_POLICY_MODULES),
        plate_core_max_known_wheel=str(wheel.get("max_known_published_version") or "") or None,
        trusted_execution_note=str(
            (raw.get("trusted_execution") or {}).get("mode")
            or "default_branch_vendored_src"
        ),
    )


def verify_modules_importable(modules: tuple[str, ...] | list[str] | None = None) -> list[str]:
    """Return error strings; empty list means all modules import successfully."""
    names = tuple(modules or REQUIRED_POLICY_MODULES)
    errors: list[str] = []
    for name in names:
        try:
            importlib.import_module(name)
        except Exception as exc:  # noqa: BLE001 — surfaced to CI
            errors.append(f"{name}: {exc}")
    return errors


def verify_modules_provenance(
    trusted_src_root: Path,
    modules: tuple[str, ...] | list[str] | None = None,
) -> list[str]:
    """Ensure loaded modules resolved under trusted_src_root (not PR workspace shadow)."""
    root = trusted_src_root.resolve()
    if not root.is_dir():
        return [f"trusted src root not found: {root}"]
    plate_root = (root / "plate_core").resolve()
    names = tuple(modules or REQUIRED_POLICY_MODULES)
    errors: list[str] = []
    for name in names:
        try:
            mod = importlib.import_module(name)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{name}: import failed: {exc}")
            continue
        mod_file = getattr(mod, "__file__", None)
        if not mod_file:
            errors.append(f"{name}: no __file__ (cannot verify provenance)")
            continue
        path = Path(mod_file).resolve()
        if not str(path).startswith(str(plate_root)):
            errors.append(
                f"{name}: loaded from {path} (expected under {plate_root})"
            )
    return errors


def describe_trust_prerequisite() -> str:
    return (
        "Authoritative branch policy requires default-branch vendored src/plate_core "
        "(git archive) or a published plate-core wheel that satisfies "
        ".agentic/policy-runtime.json. There is no PR-workspace fallback. "
        "pull_request workflow steps remain PR-editable until pinned on default branch "
        "or enforced by plate-lifecycle App; merging to release-minor does not deploy to main."
    )
