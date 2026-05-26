import unittest

from plate_core.health import HealthReport, get_health


class FakeClient:
    def __init__(self):
        self.calls = []

    def api(self, endpoint):
        self.calls.append(endpoint)
        if endpoint.startswith("repos/akasper/plate_core/labels"):
            return [
                {"name": "Bug"},
                {"name": "Feature"},
                {"name": "Epic"},
                {"name": "Documentation"},
                {"name": "Research"},
                {"name": "Design"},
                {"name": "Question"},
            ]
        if endpoint == "repos/akasper/plate_core":
            return {"default_branch": "main"}
        if endpoint == "repos/akasper/plate_core/branches/main/protection":
            return {"enabled": True}
        if endpoint.startswith("search/issues"):
            return {"total_count": 3}
        raise AssertionError(f"unexpected endpoint: {endpoint}")


class HealthTests(unittest.TestCase):
    def test_health_pass(self):
        report = get_health(repo="akasper/plate_core", client=FakeClient())
        self.assertIsInstance(report, HealthReport)
        self.assertEqual(report.repo, "akasper/plate_core")
        self.assertTrue(report.label_coverage_ok)
        self.assertEqual(report.missing_labels, [])
        self.assertTrue(report.branch_protection_enabled)
        self.assertEqual(report.open_epic_count, 3)
        self.assertEqual(report.status, "pass")


if __name__ == "__main__":
    unittest.main()

