import unittest
from unittest.mock import Mock

from plate_core.epics import get_epic_status, get_project_v2_items, add_issue_to_project_v2


class EpicStatusTests(unittest.TestCase):
    def test_get_epic_status_builds_summary(self):
        client = Mock()
        client.api.side_effect = [
            [
                {"name": "Epic"},
                {"name": "Feature"},
                {"name": "Epic: plate-core-v1"},
            ],
            {"total_count": 1},
            {"items": [{"number": 4, "title": "v1 epic", "state": "open"}], "total_count": 1},
            {"total_count": 5},
            {"total_count": 3},
        ]

        report = get_epic_status(repo="akasper/plate_core", client=client)
        self.assertEqual(report.repo, "akasper/plate_core")
        self.assertEqual(report.open_epic_count, 1)
        self.assertEqual(len(report.epics), 1)
        self.assertEqual(report.epics[0].epic_issue_number, 4)
        self.assertEqual(report.epics[0].open_child_issues, 5)
        self.assertEqual(report.epics[0].closed_child_issues, 3)

    def test_get_project_v2_items_uses_graphql(self):
        client = Mock()
        client.api.return_value = {"data": {"organization": {"projectV2": {"title": "Roadmap", "items": {"nodes": []}}}}}
        data = get_project_v2_items(repo="akasper/plate_core", project_number=1, client=client)
        self.assertEqual(data.get("title"), "Roadmap")
        # Verify it called graphql with top-level vars style
        call_args = client.api.call_args
        self.assertEqual(call_args[0][0], "graphql")
        self.assertIn("query", call_args[1]["fields"])
        self.assertIn("owner", call_args[1]["fields"])

    def test_add_issue_to_project_v2_write_path(self):
        client = Mock()
        # Simulate ID lookups + mutation success
        client.api.side_effect = [
            {"data": {"repository": {"issue": {"id": "I_123"}}}},
            {"data": {"organization": {"projectV2": {"id": "P_456"}}}},
            {"data": {"addProjectV2ItemById": {"item": {"id": "ITEM_789"}}}},
        ]
        res = add_issue_to_project_v2(42, repo="akasper/plate_core", project_number=1, client=client)
        self.assertEqual(res.get("item", {}).get("id"), "ITEM_789")
        self.assertEqual(client.api.call_count, 3)


if __name__ == "__main__":
    unittest.main()

