"""Tests for policy runtime manifest, provenance, and adopter install (#1449)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from plate_core.policy_runtime import (
    describe_trust_prerequisite,
    load_manifest,
    verify_modules_importable,
    verify_modules_provenance,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


class PolicyRuntimeTests(unittest.TestCase):
    def test_load_repo_manifest(self):
        manifest = load_manifest(REPO_ROOT / ".agentic" / "policy-runtime.json")
        self.assertGreaterEqual(manifest.schema, 1)
        self.assertIn("plate_core.issue_context", manifest.required_modules)

    def test_current_src_passes_verify(self):
        errors = verify_modules_importable()
        self.assertEqual(errors, [], msg="; ".join(errors))

    def test_provenance_rejects_shadow_path(self):
        trusted = (REPO_ROOT / "src").resolve()
        errors = verify_modules_provenance(
            trusted,
            ["plate_core.definitely_missing_module_xyz"],
        )
        self.assertTrue(errors)
        self.assertTrue(any("import failed" in e for e in errors))

    def test_provenance_accepts_repo_src(self):
        trusted = (REPO_ROOT / "src").resolve()
        errors = verify_modules_provenance(trusted, ["plate_core.issue_context"])
        self.assertEqual(errors, [])

    def test_trust_prerequisite_no_workspace_fallback(self):
        text = describe_trust_prerequisite()
        self.assertIn("no pr-workspace fallback", text.lower())
        self.assertIn("release-minor", text.lower())


class PolicyRuntimeAdopterInstallTests(unittest.TestCase):
    """Build plate-core wheel locally; install into empty adopter layout (no repo src)."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmpdir = tempfile.mkdtemp(prefix="plate-adopter-")
        cls.wheel_dir = Path(cls._tmpdir) / "wheels"
        cls.wheel_dir.mkdir()
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "wheel",
                str(REPO_ROOT),
                "-w",
                str(cls.wheel_dir),
                "--no-deps",
                "-q",
            ],
            check=True,
            cwd=str(REPO_ROOT),
        )
        cls.wheels = sorted(cls.wheel_dir.glob("plate_core*.whl"))
        if not cls.wheels:
            raise unittest.SkipTest("wheel build produced no plate_core wheel")

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls._tmpdir, ignore_errors=True)

    def _isolated_run(self, *, target: Path, adopter_root: Path, extra_env: dict | None = None) -> subprocess.CompletedProcess[str]:
        empty_cwd = adopter_root / "exec-cwd"
        empty_cwd.mkdir(parents=True, exist_ok=True)
        env = {
            **os.environ,
            "PYTHONPATH": str(target),
            "PYTHONNOUSERSITE": "1",
        }
        if extra_env:
            env.update(extra_env)
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "plate_core.policy_runtime_verify",
                "--root",
                str(adopter_root),
            ],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(empty_cwd),
        )

    def test_built_wheel_satisfies_manifest_in_isolated_target(self):
        adopter_root = Path(self._tmpdir) / "adopter-ok"
        target = adopter_root / "site-packages"
        target.mkdir(parents=True)
        (adopter_root / ".agentic").mkdir()
        shutil.copy(
            REPO_ROOT / ".agentic" / "policy-runtime.json",
            adopter_root / ".agentic" / "policy-runtime.json",
        )
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "-q",
                "--no-deps",
                "--target",
                str(target),
                str(self.wheels[0]),
            ],
            check=True,
        )
        proc = self._isolated_run(target=target, adopter_root=adopter_root)
        self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)

    def test_pypi_090_insufficient_in_isolated_target(self):
        adopter_root = Path(self._tmpdir) / "adopter-bad"
        target = adopter_root / "site-packages"
        target.mkdir(parents=True)
        (adopter_root / ".agentic").mkdir()
        manifest = {
            "schema": 1,
            "plate_core_wheel": {
                "max_known_published_version": "0.9.0",
                "required_modules": [
                    "plate_core.pr_integration_base_gate",
                    "plate_core.issue_context",
                ],
            },
        }
        (adopter_root / ".agentic" / "policy-runtime.json").write_text(
            json.dumps(manifest),
            encoding="utf-8",
        )
        proc_install = subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "-q",
                "--no-deps",
                "--target",
                str(target),
                "plate-core==0.9.0",
            ],
            capture_output=True,
            text=True,
        )
        if proc_install.returncode != 0:
            self.skipTest(f"PyPI plate-core==0.9.0 not installable: {proc_install.stderr}")
        proc = self._isolated_run(target=target, adopter_root=adopter_root)
        self.assertNotEqual(proc.returncode, 0)
        combined = (proc.stderr or "") + (proc.stdout or "")
        self.assertTrue(
            "policy_runtime_verify" in combined
            or "pr_integration_base_gate" in combined
            or "policy-runtime" in combined.lower(),
            msg=combined,
        )


if __name__ == "__main__":
    unittest.main()
