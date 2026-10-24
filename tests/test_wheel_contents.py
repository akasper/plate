"""Regression tests for plate-core wheel packaging (#1115)."""

from __future__ import annotations

import json
import importlib.util
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PAYLOAD_SRC = REPO_ROOT / "src" / "plate_core" / "template_payload"
INVENTORY_PATH = REPO_ROOT / "src" / "plate_core" / "data" / "template_payload_inventory.json"
WHEEL_PREFIX = "plate_core/template_payload/"
LABELS_PATHS = (
    REPO_ROOT / ".github" / "labels.yml",
    TEMPLATE_PAYLOAD_SRC / ".github" / "labels.yml",
)


def _template_payload_source_paths() -> set[str]:
    paths: set[str] = set()
    for path in TEMPLATE_PAYLOAD_SRC.rglob("*"):
        if not path.is_file():
            continue
        if "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        paths.add(path.relative_to(TEMPLATE_PAYLOAD_SRC).as_posix())
    return paths


def _wheel_template_payload_paths(wheel_path: Path) -> set[str]:
    paths: set[str] = set()
    with zipfile.ZipFile(wheel_path) as archive:
        for name in archive.namelist():
            if not name.startswith(WHEEL_PREFIX) or name.endswith("/"):
                continue
            paths.add(name[len(WHEEL_PREFIX) :])
    return paths


def _read_wheel_metadata(wheel_path: Path) -> str:
    with zipfile.ZipFile(wheel_path) as archive:
        meta_names = [n for n in archive.namelist() if n.endswith(".dist-info/METADATA")]
        if not meta_names:
            raise AssertionError(f"No METADATA in wheel {wheel_path}")
        return archive.read(meta_names[0]).decode("utf-8")


def _inventory_template_payload_paths() -> set[str]:
    inventory = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    files = inventory.get("files", [])
    return {item["path"] for item in files if isinstance(item, dict) and item.get("path")}


class TestWheelContents(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if importlib.util.find_spec("setuptools") is None or importlib.util.find_spec("wheel") is None:
            raise unittest.SkipTest(
                "setuptools and wheel are required to build a plate-core wheel for this test"
            )
        cls._wheel_dir = Path(tempfile.mkdtemp(prefix="plate-wheel-test-"))
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "wheel",
                ".",
                "--no-deps",
                "--no-build-isolation",
                "-w",
                str(cls._wheel_dir),
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            raise AssertionError(
                "pip wheel failed (packaging regression):\n"
                f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
            )
        wheels = sorted(cls._wheel_dir.glob("plate_core-*.whl"))
        if not wheels:
            raise AssertionError("pip wheel succeeded but produced no plate_core-*.whl")
        cls.wheel_path = wheels[-1]

    @classmethod
    def tearDownClass(cls) -> None:
        wheel_dir = getattr(cls, "_wheel_dir", None)
        if wheel_dir is not None and wheel_dir.exists():
            shutil.rmtree(wheel_dir, ignore_errors=True)

    def test_template_payload_matches_source_tree(self) -> None:
        expected = _template_payload_source_paths()
        actual = _wheel_template_payload_paths(self.wheel_path)
        self.assertEqual(expected, actual)

    def test_wheel_matches_template_payload_inventory(self) -> None:
        expected = _inventory_template_payload_paths()
        self.assertGreater(len(expected), 0, "template_payload_inventory.json lists no files")
        actual = _wheel_template_payload_paths(self.wheel_path)
        missing = sorted(expected - actual)
        self.assertEqual(
            [],
            missing,
            msg=f"wheel missing {len(missing)} template_payload file(s) from inventory: "
            f"{missing[:10]}{'...' if len(missing) > 10 else ''}",
        )

    def test_wheel_includes_key_payload_paths(self) -> None:
        names = _wheel_template_payload_paths(self.wheel_path)
        self.assertIn(".github/labels.yml", names)
        self.assertTrue(any(n.startswith(".github/ISSUE_TEMPLATE/") and n.endswith(".yml") for n in names))
        self.assertIn(".agentic/skills.yml", names)
        self.assertTrue(any(n.startswith("scripts/") for n in names))

    def test_wheel_metadata_declares_pyyaml(self) -> None:
        metadata = _read_wheel_metadata(self.wheel_path)
        self.assertIsNotNone(re.search(r"^Requires-Dist: pyyaml", metadata, flags=re.MULTILINE))


class TestLabelsRegistry(unittest.TestCase):
    def test_label_descriptions_within_github_limit(self) -> None:
        for path in LABELS_PATHS:
            labels = yaml.safe_load(path.read_text(encoding="utf-8"))
            self.assertIsInstance(labels, list)
            for entry in labels:
                if not isinstance(entry, dict):
                    continue
                desc = entry.get("description", "")
                self.assertLessEqual(
                    len(desc),
                    100,
                    msg=f"{path.name} label {entry.get('name')!r} description is {len(desc)} chars",
                )

    def test_status_stub_label_present(self) -> None:
        for path in LABELS_PATHS:
            labels = yaml.safe_load(path.read_text(encoding="utf-8"))
            names = {entry.get("name") for entry in labels if isinstance(entry, dict)}
            self.assertIn("status:stub", names, msg=str(path))


if __name__ == "__main__":
    unittest.main()
