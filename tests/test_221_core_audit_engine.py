"""Initial tests for Core Information Audit engine (Epic #218 / Feature #221).

Tests the MCP tool interface and stub behavior per the contract (#223) and model (#220).
This is the 'tests first' skeleton; full engine logic, integration, and E2E will expand
in follow-up commits for this issue (one coherent PR per PLATE Feature process).
"""

import unittest

from plate_core.mcp.audit_tools import PerformInformationAuditTool


class TestPerformInformationAuditTool(unittest.TestCase):
    def test_execute_basic_stub(self):
        res = PerformInformationAuditTool.execute(
            repo="akasper/plate",
            dry_run=True,
            max_questions=3,
            include_defaults=True,
        )
        self.assertIn("proposed_questions", res)
        self.assertIn("audit_log", res)
        self.assertIn("count", res)
        self.assertLessEqual(len(res["proposed_questions"]), 3)
        self.assertTrue(res["dry_run"])

    def test_proposed_have_required_fields(self):
        res = PerformInformationAuditTool.execute(
            repo="akasper/plate",
            dry_run=True,
            max_questions=1,
            include_defaults=True,
        )
        self.assertGreaterEqual(len(res["proposed_questions"]), 1)
        q = res["proposed_questions"][0]
        for key in ("title", "body", "related_goals", "provenance", "priority_rationale"):
            self.assertIn(key, q)
            self.assertTrue(q[key], f"{key} should be non-empty in proposal")

    def test_goals_page_signal_affects_output(self):
        # When Goals present (as on this branch), we expect a refinement-style proposal
        # (the stub detects Mission etc.). This exercises the Goals-driven path from #220/#223.
        res = PerformInformationAuditTool.execute(
            repo="akasper/plate",
            dry_run=True,
            max_questions=2,
            include_defaults=True,
        )
        titles = [p["title"] for p in res["proposed_questions"]]
        # At least the default or a Goals-derived one should appear
        self.assertTrue(
            any("Mission" in t or "Goals" in t or "risks" in t.lower() for t in titles),
            "Expected proposals grounded in Goals page or defaults per design",
        )

    def test_respects_max_questions(self):
        res = PerformInformationAuditTool.execute(
            repo="akasper/plate",
            dry_run=True,
            max_questions=1,
        )
        self.assertLessEqual(len(res["proposed_questions"]), 1)


if __name__ == "__main__":
    unittest.main()
