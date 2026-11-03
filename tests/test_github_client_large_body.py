"""Regression: large ``content`` fields must use ``gh api --input -``, not argv (#1030)."""

import base64
import json
import unittest
from unittest.mock import MagicMock, patch

from plate_core.bootstrap import _put_repository_file
from plate_core.github_client import GhClient

# Per-argument size limit on Linux cited in akasper/plate#1030.
_LINUX_ARGV_CONTENT_LIMIT = 128 * 1024


class LargeContentUsesStdinTests(unittest.TestCase):
    """``_fields_require_json_input`` routes large contents bodies to stdin."""

    def test_content_over_128kb_not_on_argv(self):
        """A >128 KB ``content`` value must go via ``--input -``, not ``-f`` argv."""
        big = "B" * (_LINUX_ARGV_CONTENT_LIMIT + 1)
        with patch("plate_core.github_client.run_hidden") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="{}", stderr="")
            GhClient().api(
                "repos/owner/repo/contents/large.bin",
                method="PUT",
                fields={"message": "add", "content": big, "branch": "main"},
            )
            cmd = mock_run.call_args[0][0]
            self.assertIn("--input", cmd)
            idx = cmd.index("--input")
            self.assertEqual(cmd[idx + 1], "-")
            joined = " ".join(cmd)
            self.assertNotIn(big, joined)
            self.assertNotIn(big[:4096], joined)
            parsed = json.loads(mock_run.call_args[1]["input"])
            self.assertEqual(parsed["content"], big)

    def test_bootstrap_put_repository_file_over_128kb_uses_stdin(self):
        """``bootstrap._put_repository_file`` (contents PUT) must not pass huge ``content`` on argv."""
        encoded_bytes = b"z" * (_LINUX_ARGV_CONTENT_LIMIT + 1)
        expected_b64 = base64.b64encode(encoded_bytes).decode("ascii")
        self.assertGreater(len(expected_b64), _LINUX_ARGV_CONTENT_LIMIT)

        with patch("plate_core.github_client.run_hidden") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="{}", stderr="")
            _put_repository_file(
                GhClient(),
                "owner/repo",
                "templates/big.dat",
                message="bootstrap upload",
                encoded_bytes=encoded_bytes,
                branch="main",
            )
            cmd = mock_run.call_args[0][0]
            self.assertIn("repos/owner/repo/contents/templates/big.dat", cmd)
            self.assertIn("-X", cmd)
            self.assertIn("PUT", cmd)
            self.assertIn("--input", cmd)
            joined = " ".join(cmd)
            self.assertNotIn(expected_b64, joined)
            self.assertNotIn(expected_b64[:4096], joined)
            parsed = json.loads(mock_run.call_args[1]["input"])
            self.assertEqual(parsed["content"], expected_b64)
            self.assertEqual(parsed["message"], "bootstrap upload")
            self.assertEqual(parsed["branch"], "main")


if __name__ == "__main__":
    unittest.main()
