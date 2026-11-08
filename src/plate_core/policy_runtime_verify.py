"""CLI: verify policy runtime imports from PYTHONPATH (#1449)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from plate_core.policy_runtime import (
    DEFAULT_MANIFEST,
    load_manifest,
    verify_modules_importable,
    verify_modules_provenance,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify PLATE policy runtime imports")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="Path to .agentic/policy-runtime.json",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Trusted runtime root (manifest lives under this tree)",
    )
    parser.add_argument(
        "--require-provenance",
        type=Path,
        default=None,
        help="Require imported modules' __file__ under this trusted src root",
    )
    args = parser.parse_args(argv)
    manifest_path = args.manifest
    if args.root is not None:
        candidate = args.root / ".agentic" / "policy-runtime.json"
        if candidate.is_file():
            manifest_path = candidate
    if not manifest_path.is_file():
        print(
            f"## ⚠️ policy-runtime\n\nMissing manifest: {manifest_path}",
            file=sys.stderr,
        )
        return 1
    manifest = load_manifest(manifest_path)
    errors = verify_modules_importable(manifest.required_modules)
    if args.require_provenance is not None:
        errors.extend(
            verify_modules_provenance(
                args.require_provenance,
                manifest.required_modules,
            )
        )
    if errors:
        print("## ⚠️ policy-runtime\n", file=sys.stderr)
        for line in errors:
            print(line, file=sys.stderr)
        print(
            "\nSee docs/design/trusted-policy-runtime-threat-model-1449.md and "
            ".agentic/policy-runtime.json.",
            file=sys.stderr,
        )
        return 1
    print(
        f"policy runtime ok ({len(manifest.required_modules)} modules, "
        f"mode={manifest.trusted_execution_note})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
