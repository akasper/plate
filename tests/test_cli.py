import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from plate_core.cli import main
from plate_core.health import HealthReport


class CliTests(unittest.TestCase):
    @patch("plate_core.cli.get_health")
    def test_health_json_output(self, mock_get_health):
        mock_get_health.return_value = HealthReport(
            repo="akasper/plate_core",
            label_coverage_ok=True,
            missing_labels=[],
            branch_protection_enabled=True,
            open_epic_count=2,
            status="pass",
        )
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(["health", "--repo", "akasper/plate_core", "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(out.getvalue().strip())
        self.assertEqual(payload["repo"], "akasper/plate_core")
        self.assertEqual(payload["status"], "pass")


if __name__ == "__main__":
    unittest.main()

