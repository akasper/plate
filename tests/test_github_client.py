"""Tests for GhClient field serialization."""

import unittest
from unittest.mock import MagicMock, patch

from plate_core.github_client import GhClient


class GhClientFieldSerializationTests(unittest.TestCase):
    """Verify that GhClient chooses -f vs -F correctly to prevent type mis-inference."""

    def _captured_cmd(self, fields: dict) -> list[str]:
        """Run GhClient.api with given fields and return the command that would have been executed."""
        with patch("plate_core.github_client.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="{}", stderr="")
            GhClient().api("repos/owner/repo", method="PATCH", fields=fields)
            return mock_run.call_args[0][0]

    def test_string_uses_dash_f(self):
        """String values must use -f (raw) to prevent type mis-inference."""
        cmd = self._captured_cmd({"color": "5319e7"})
        self.assertIn("-f", cmd)
        self.assertIn("color=5319e7", cmd)
        # Crucially, -F must NOT appear immediately before color= since that
        # would cause gh to parse 5319e7 as scientific notation.
        flag_idx = cmd.index("color=5319e7") - 1
        self.assertEqual(cmd[flag_idx], "-f", "String field color must be preceded by -f")

    def test_bool_true_uses_dash_F(self):
        """Boolean True must use -F with value 'true' so gh sends a JSON boolean."""
        cmd = self._captured_cmd({"has_wiki": True})
        idx = next(i for i, v in enumerate(cmd) if v == "has_wiki=true")
        self.assertEqual(cmd[idx - 1], "-F", "Boolean field must use -F")

    def test_bool_false_uses_dash_F(self):
        """Boolean False must use -F with value 'false'."""
        cmd = self._captured_cmd({"private": False})
        idx = next(i for i, v in enumerate(cmd) if v == "private=false")
        self.assertEqual(cmd[idx - 1], "-F", "Boolean field must use -F")

    def test_int_uses_dash_F(self):
        """Integer values must use -F."""
        cmd = self._captured_cmd({"limit": 10})
        idx = next(i for i, v in enumerate(cmd) if v == "limit=10")
        self.assertEqual(cmd[idx - 1], "-F", "Integer field must use -F")

    def test_hex_color_not_interpreted_as_scientific_notation(self):
        """Regression: '5319e7' (hex color) must not become scientific notation."""
        cmd = self._captured_cmd({"color": "5319e7", "has_wiki": True})
        # color must use -f
        color_idx = cmd.index("color=5319e7") - 1
        self.assertEqual(cmd[color_idx], "-f")
        # has_wiki must use -F
        wiki_idx = cmd.index("has_wiki=true") - 1
        self.assertEqual(cmd[wiki_idx], "-F")


if __name__ == "__main__":
    unittest.main()
