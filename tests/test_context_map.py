import unittest
from pathlib import Path

from plate_core.context_map import get_context_route, list_context_routes, render_context_map_markdown


REPO_ROOT = Path(__file__).resolve().parents[1]


class ContextMapTests(unittest.TestCase):
    def test_context_map_contains_release_and_delegation_routes(self):
        routes = list_context_routes()
        route_ids = {route.id for route in routes}
        self.assertIn("release-targeting", route_ids)
        self.assertIn("delegation", route_ids)

    def test_release_targeting_route_points_to_release_status(self):
        route = get_context_route("release-targeting")
        self.assertEqual("Run `gh plate release status`.", route.first_step)
        self.assertIn("gh plate release status", route.machine_surfaces)
        self.assertIn("AGENTS.md §Branch Model and Ceremonies", route.authoritative_artifacts)

    def test_context_map_wiki_page_matches_rendered_output(self):
        doc_path = REPO_ROOT / "docs" / "wiki" / "Agent-Context-Map.md"
        self.assertEqual(render_context_map_markdown(), doc_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
