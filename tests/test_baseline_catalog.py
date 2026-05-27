import unittest
from unittest.mock import patch

from plate_core import baseline_catalog
from plate_core.baseline_catalog import BaselineCatalogError, load_baseline_catalog


class BaselineCatalogTests(unittest.TestCase):
    def test_load_baseline_catalog_returns_twelve_agents(self):
        catalog = load_baseline_catalog()
        self.assertEqual(12, len(catalog.agents))
        agent_ids = {agent.id for agent in catalog.agents}
        self.assertIn("project-manager", agent_ids)
        self.assertIn("research-agent", agent_ids)

    def test_agent_skill_references_are_resolved(self):
        catalog = load_baseline_catalog()
        skill_ids = {skill.id for skill in catalog.skills}
        for agent in catalog.agents:
            for skill_id in agent.primary_skill_ids:
                self.assertIn(skill_id, skill_ids)

    def test_skills_track_owning_agents(self):
        catalog = load_baseline_catalog()
        agent_ids = {agent.id for agent in catalog.agents}
        for skill in catalog.skills:
            self.assertGreater(len(skill.owning_agent_ids), 0)
            for agent_id in skill.owning_agent_ids:
                self.assertIn(agent_id, agent_ids)

    def test_invalid_schema_version_raises(self):
        load_baseline_catalog.cache_clear()
        with patch("plate_core.baseline_catalog._load_yaml", return_value={"schema_version": 2, "agents": [], "skills": []}):
            with self.assertRaises(BaselineCatalogError):
                load_baseline_catalog()
        load_baseline_catalog.cache_clear()


if __name__ == "__main__":
    unittest.main()
