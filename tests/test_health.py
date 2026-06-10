import json
import unittest

from plate_core.github_client import GhApiError
from plate_core.health import HealthReport, get_health


class FakeClient:
    def __init__(self):
        self.calls = []

    def api(self, endpoint, **kwargs):  # tolerate retries= etc from resilient client
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
                {"name": "Task"},
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
        if "contents/.plate" in endpoint:
            # Simulate valid .plate
            import base64
            content = json.dumps({"version": "1.0"}).encode()
            return {"name": ".plate", "type": "file", "encoding": "base64", "content": base64.b64encode(content).decode()}
        if "contents/docs/curiosity/answers.yml" in endpoint or "contents/docs/curiosity/answers.json" in endpoint:
            return {"name": "answers.yml", "type": "file"}
        if "contents/AGENTS.md" in endpoint:
            return {"name": "AGENTS.md", "type": "file"}
        if "contents/.agentic" in endpoint:
            return {"name": ".agentic", "type": "dir"}
        raise AssertionError(f"unexpected endpoint: {endpoint}")


class FailingClient:
    """Simulates partial failures for resilience tests (#270)."""
    def __init__(self):
        self.calls = 0

    def api(self, endpoint, **kwargs):
        self.calls += 1
        if "labels" in endpoint:
            return [{"name": "Bug"}, {"name": "Feature"}]  # partial labels
        if "search/issues" in endpoint:
            raise GhApiError("rate limit on search")
        if "protection" in endpoint:
            raise GhApiError("404 no protection")
        if endpoint == "repos/akasper/plate_core" or endpoint.endswith("/akasper/plate_core"):
            return {"default_branch": "main"}
        return {}


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
        self.assertEqual(report.errors, [])  # no partial errors
        self.assertTrue(report.goals_page_present)
        self.assertEqual(report.open_question_count, 2)
        self.assertTrue(report.plate_config_present)
        self.assertTrue(report.plate_config_valid)
        self.assertEqual(report.plate_config_file_version, "1.0")
        self.assertEqual(report.plate_config_resolved_version, "1.1")
        self.assertTrue(report.plate_config_upgrade_available)
        self.assertIn(".plate/config present", report.plate_repo_signals)  # #459 / #464 detection for default persona

    def test_health_partial_on_failures(self):
        """Degraded mode with errors list when some calls fail (rate, 404 etc)."""
        client = FailingClient()
        report = get_health(repo="akasper/plate_core", client=client)
        self.assertIsInstance(report, HealthReport)
        self.assertFalse(report.label_coverage_ok)  # missing many
        self.assertGreater(len(report.missing_labels), 0)
        self.assertFalse(report.branch_protection_enabled)
        self.assertEqual(report.open_epic_count, 0)  # failed search
        self.assertTrue(len(report.errors) >= 2)  # at least protection + search
        self.assertIn("rate limit", " ".join(report.errors))
        self.assertEqual(report.status, "warn")  # some ok (labels partial succeeded)
        # to_dict omits empty errors
        d = report.to_dict()
        self.assertIn("errors", d)
        self.assertTrue(d["errors"])

    def test_health_label_coverage_case_insensitive(self):
        """Health tolerates GH canonical casing (e.g. 'question' vs 'Question' in REQUIRED)."""
        class LowerQuestionClient(FakeClient):
            def api(self, endpoint, **kwargs):
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
                        {"name": "Task"},
                    ]
                return FakeClient.api(self, endpoint, **kwargs)

        report = get_health(repo="akasper/plate_core", client=LowerQuestionClient())
        self.assertTrue(report.label_coverage_ok)
        self.assertEqual(report.missing_labels, [])
        self.assertEqual(report.status, "pass")
        self.assertTrue(report.goals_page_present)
        self.assertEqual(report.open_question_count, 2)
        self.assertTrue(report.plate_config_present)
        self.assertTrue(report.plate_config_valid)
        self.assertEqual(report.plate_config_file_version, "1.0")
        self.assertEqual(report.plate_config_resolved_version, "1.1")
        self.assertTrue(report.plate_config_upgrade_available)
        self.assertTrue(report.curiosity_answers_present)


if __name__ == "__main__":
    unittest.main()
