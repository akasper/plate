"""Tests for gh-plate ↔ plate-core version locking (#614)."""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


def _load_gh_plate():
    root = Path(__file__).resolve().parents[1]
    path = root / "gh-plate"
    # File has no .py suffix (gh extension name); use SourceFileLoader.
    loader = importlib.machinery.SourceFileLoader("gh_plate_launcher", str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


class TestGhPlateVersionLock(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load_gh_plate()

    def test_normalize_version(self):
        n = self.mod.normalize_version
        self.assertEqual(n("v0.7.2"), "0.7.2")
        self.assertEqual(n("0.7.2"), "0.7.2")
        self.assertEqual(n("  v1.0.0\n"), "1.0.0")
        self.assertIsNone(n(""))
        self.assertIsNone(n(None))

    def test_read_pin_from_version_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "VERSION").write_text("v0.7.2\n", encoding="utf-8")
            self.assertEqual(self.mod.read_pinned_version(tmp), "0.7.2")
            Path(tmp, "PLATE_CORE_VERSION").write_text("0.8.0\n", encoding="utf-8")
            # PLATE_CORE_VERSION file wins over VERSION
            self.assertEqual(self.mod.read_pinned_version(tmp), "0.8.0")

    def test_read_pin_from_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "VERSION").write_text("v0.1.0\n", encoding="utf-8")
            with patch.dict("os.environ", {"PLATE_CORE_VERSION": "v9.9.9"}, clear=False):
                self.assertEqual(self.mod.read_pinned_version(tmp), "9.9.9")

    def test_dev_checkout_skips_pip(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "src" / "plate_core").mkdir(parents=True)
            Path(tmp, "VERSION").write_text("v0.7.2\n", encoding="utf-8")
            with patch.object(self.mod, "_pip_install") as pip:
                with patch.dict("os.environ", {"PLATE_CORE_FORCE_PIN": ""}, clear=False):
                    # clear force pin
                    import os

                    os.environ.pop("PLATE_CORE_FORCE_PIN", None)
                    out = self.mod.ensure_plate_core(script_dir=tmp, force_pin=False)
            self.assertEqual(out["action"], "dev_skip")
            pip.assert_not_called()

    def test_pin_installs_when_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "VERSION").write_text("v0.7.2\n", encoding="utf-8")
            with patch.object(self.mod, "get_installed_plate_core_version", side_effect=[None, "0.7.2"]):
                with patch.object(self.mod, "_pip_install") as pip:
                    out = self.mod.ensure_plate_core(script_dir=tmp, force_pin=True)
            self.assertEqual(out["action"], "installed")
            pip.assert_called_once_with("plate-core==0.7.2")

    def test_pin_reinstalls_on_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "PLATE_CORE_VERSION").write_text("0.7.2\n", encoding="utf-8")
            with patch.object(
                self.mod, "get_installed_plate_core_version", side_effect=["0.9.0", "0.7.2"]
            ):
                with patch.object(self.mod, "_pip_install") as pip:
                    out = self.mod.ensure_plate_core(script_dir=tmp, force_pin=True)
            self.assertEqual(out["action"], "reinstalled")
            pip.assert_called_once_with("plate-core==0.7.2")

    def test_pin_ok_when_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "VERSION").write_text("0.7.2\n", encoding="utf-8")
            with patch.object(self.mod, "get_installed_plate_core_version", return_value="0.7.2"):
                with patch.object(self.mod, "_pip_install") as pip:
                    out = self.mod.ensure_plate_core(script_dir=tmp, force_pin=True)
            self.assertEqual(out["action"], "ok")
            pip.assert_not_called()


if __name__ == "__main__":
    unittest.main()
