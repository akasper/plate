"""Tests for GhClient field serialization and resilience (#270 error/rate/secret)."""

import unittest
from unittest.mock import MagicMock, patch

from plate_core.github_client import GhClient, GhApiError, _sanitize_error


class GhClientFieldSerializationTests(unittest.TestCase):
    """Verify that GhClient chooses -f vs -F correctly to prevent type mis-inference."""

    def _captured_cmd(self, fields: dict) -> list[str]:
        """Run GhClient.api with given fields and return the command that would have been executed."""
        with patch("plate_core.github_client.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="{}", stderr="")
            GhClient().api("repos/owner/repo", method="PATCH", fields=fields)
            return mock_run.call_args[0][0]

    def test_get_requests_force_get_method_even_with_fields(self):
        """GET requests with query fields must stay GET so gh does not reinterpret them as POST."""
        with patch("plate_core.github_client.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="{}", stderr="")
            GhClient().api("repos/owner/repo/issues", fields={"labels": "Question"})
            cmd = mock_run.call_args[0][0]
        self.assertEqual(cmd[:5], ["gh", "api", "repos/owner/repo/issues", "-X", "GET"])

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


class GhClientResilienceTests(unittest.TestCase):
    """Retry/backoff, rate limit tolerance, secret redaction (#270)."""

    def test_sanitize_redacts_tokens(self):
        msg = "Bad credentials for token ghp_ABC123def456 or Bearer xyz"
        safe = _sanitize_error(msg)
        self.assertNotIn("ghp_ABC123def456", safe)
        self.assertNotIn("xyz", safe)
        self.assertIn("[REDACTED]", safe)

    def test_api_retries_on_transient_and_succeeds(self):
        with patch("plate_core.github_client.subprocess.run") as mock_run:
            # First two fail (rate), third succeeds
            mock_run.side_effect = [
                MagicMock(returncode=1, stdout="", stderr="API rate limit exceeded"),
                MagicMock(returncode=1, stdout="", stderr="temporary error"),
                MagicMock(returncode=0, stdout='{"ok":true}', stderr=""),
            ]
            client = GhClient()
            result = client.api("repos/o/r", retries=3, base_backoff=0.01)
            self.assertEqual(result, {"ok": True})
            self.assertEqual(mock_run.call_count, 3)

    def test_api_raises_after_retries_exhausted(self):
        with patch("plate_core.github_client.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="rate limit")
            client = GhClient()
            with self.assertRaises(GhApiError) as ctx:
                client.api("repos/o/r", retries=2, base_backoff=0.01)
            self.assertIn("rate limit", str(ctx.exception))
            self.assertEqual(mock_run.call_count, 2)


class GhClientDiscussionsTests(unittest.TestCase):
    """Feature #329: GhClient discussion helpers (REST + GraphQL paths for #329 MCP surface)."""

    def test_list_discussions_builds_endpoint_and_passes_params(self):
        with patch("plate_core.github_client.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout='[{"number":54,"title":"foo"}]', stderr="")
            res = GhClient().list_discussions("akasper", "plate", per_page=5, state="open")
            cmd = mock_run.call_args[0][0]
            self.assertIn("repos/akasper/plate/discussions", cmd)
            self.assertIn("-f", cmd)
            joined = " ".join(cmd)
            self.assertIn("per_page=5", joined)
            self.assertEqual(res, [{"number": 54, "title": "foo"}])

    def test_create_discussion_uses_graphql_and_resolves_repo_id(self):
        # Simulate two calls: repo id query, then mutation
        responses = [
            MagicMock(returncode=0, stdout='{"data":{"repository":{"id":"R_123"}} }', stderr=""),
            MagicMock(returncode=0, stdout='{"data":{"createDiscussion":{"discussion":{"number":999,"title":"new"}}}}', stderr=""),
        ]
        with patch("plate_core.github_client.subprocess.run", side_effect=responses) as mock_run:
            res = GhClient().create_discussion("akasper", "plate", category_id="DIC_foo", title="t", body="b")
            self.assertEqual(res.get("number"), 999)
            # At least 2 calls made
            self.assertGreaterEqual(mock_run.call_count, 2)


if __name__ == "__main__":
    unittest.main()
