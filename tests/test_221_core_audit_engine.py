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
        # (the stub detects Mission etc.). This exercises the Goals-driven path from #220/#223
        # (isolated by disabling defaults from catalog #222).
        res = PerformInformationAuditTool.execute(
            repo="akasper/plate",
            dry_run=True,
            max_questions=5,
            include_defaults=True,
        )
        titles = [p["title"] for p in res["proposed_questions"]]
        # At least a Goals-derived refinement should appear
        self.assertTrue(
            any("Mission" in t or "Goals" in t or "risks" in t.lower() for t in titles),
            "Expected proposals grounded in Goals page per design",
        )

    def test_respects_max_questions(self):
        res = PerformInformationAuditTool.execute(
            repo="akasper/plate",
            dry_run=True,
            max_questions=1,
        )
        self.assertLessEqual(len(res["proposed_questions"]), 1)

    def test_baseline_catalog_loads_informational_goals(self):
        from plate_core.baseline_catalog import load_baseline_catalog
        catalog = load_baseline_catalog()
        goals = catalog.informational_goals
        self.assertGreater(len(goals), 0)
        ids = {g.id for g in goals}
        self.assertIn("primary-purpose", ids)
        self.assertIn("primary-users", ids)
        self.assertTrue(all(g.title and g.body for g in goals))

    def test_catalog_supports_extension_goals(self):
        from plate_core.baseline_catalog import load_baseline_catalog
        catalog = load_baseline_catalog()
        goals = catalog.informational_goals
        ext_goals = [g for g in goals if g.provided_by != "platform"]
        self.assertGreater(len(ext_goals), 0)
        self.assertTrue(all(g.provided_by for g in ext_goals))
        ids = {g.id for g in ext_goals}
        self.assertIn("marketing-gtm-positioning", ids)
        self.assertIn("technical-architecture-risks", ids)

    def test_audit_includes_defaults_from_catalog(self):
        # With include_defaults, proposals should come from the catalog (post #222)
        res = PerformInformationAuditTool.execute(
            repo="akasper/plate",
            dry_run=True,
            max_questions=10,
            include_defaults=True,
        )
        titles = [p["title"] for p in res["proposed_questions"]]
        # Should include at least the catalog ones (not just Goals-derived)
        self.assertTrue(
            any("primary-purpose" in t.lower() or "purpose or value" in t.lower() for t in titles),
            "Expected catalog defaults in audit proposals",
        )

    def test_agent_guidance_includes_audit_section(self):
        # For #225: guidance exercised; new section present for Information Audits/Goals.
        from plate_core.agent_guidance import get_agent_guidance_sections
        sections = get_agent_guidance_sections()
        self.assertIn("information_audit", sections)
        self.assertIn("Information Audits and Goals Page", sections["information_audit"])
        self.assertIn("plate_perform_information_audit", sections["information_audit"])

    def test_audit_produces_extension_goals(self):
        # For #227 harness/tests: verify audit includes extension-provided goals (#226).
        res = PerformInformationAuditTool.execute(
            repo="akasper/plate",
            dry_run=True,
            max_questions=20,
            include_defaults=True,
        )
        titles = [p["title"] for p in res["proposed_questions"]]
        self.assertTrue(
            any("value prop" in t.lower() or "positioning" in t.lower() or "gtm" in t.lower() or "marketing" in t.lower() for t in titles),
            "Expected extension goals from catalog in audit proposals",
        )
        self.assertTrue(
            any("architectural" in t.lower() or "tech debt" in t.lower() or "architecture" in t.lower() for t in titles),
            "Expected extension goals from catalog in audit proposals",
        )

    def test_catalog_has_platform_and_extension(self):
        # #227 coverage: distinguish platform vs extension goals.
        from plate_core.baseline_catalog import load_baseline_catalog
        catalog = load_baseline_catalog()
        platform = [g for g in catalog.informational_goals if g.provided_by == "platform"]
        ext = [g for g in catalog.informational_goals if g.provided_by != "platform"]
        self.assertGreater(len(platform), 0)
        self.assertGreater(len(ext), 0)


if __name__ == "__main__":
    unittest.main()
