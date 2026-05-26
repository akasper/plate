import unittest
from unittest.mock import Mock

from plate_core.epics import get_epic_status


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


if __name__ == "__main__":
    unittest.main()

