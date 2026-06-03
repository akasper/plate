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
            if "label:Question" in endpoint:
                return {"total_count": 2}
            return {"total_count": 3}
        if "contents/docs/wiki/Goals.md" in endpoint:
            return {"name": "Goals.md", "type": "file"}
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
        self.assertEqual(report.binary_artifacts_tracked, 0)  # hygiene regression guard for #90
        self.assertEqual(report.status, "pass")
        self.assertTrue(report.goals_page_present)
        self.assertEqual(report.open_question_count, 2)

    def test_health_label_coverage_case_insensitive(self):
        """Health tolerates GH canonical casing (e.g. 'question' vs 'Question' in REQUIRED)."""
        class LowerQuestionClient(FakeClient):
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
                        {"name": "question"},  # GH often returns lowercase
                    ]
                # delegate others to super via instance
                return super().api(endpoint) if hasattr(super(), 'api') else FakeClient.api(self, endpoint)

        report = get_health(repo="akasper/plate_core", client=LowerQuestionClient())
        self.assertTrue(report.label_coverage_ok)
        self.assertEqual(report.missing_labels, [])
        self.assertEqual(report.status, "pass")
        self.assertTrue(report.goals_page_present)
        self.assertEqual(report.open_question_count, 2)


if __name__ == "__main__":
    unittest.main()

