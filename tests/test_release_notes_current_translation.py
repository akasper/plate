import json
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_release(version: str) -> dict:
    path = REPO_ROOT / ".agentic" / "releases" / f"v{version}.json"
    return json.loads(path.read_text(encoding="utf-8"))


class CurrentMdTranslationReleaseNotesTests(unittest.TestCase):
    def test_backfill_release_exists_for_current_md_translation(self):
        release_path = REPO_ROOT / ".agentic" / "releases" / "v0.1.2.json"
        self.assertTrue(
            release_path.exists(),
            "Missing v0.1.2 release-note backfill for CURRENT.md translation.",
        )

    def test_backfill_release_tracks_existing_capabilities(self):
        release = load_release("0.1.2")
        entry_text = "\n".join(entry.get("migration_impact", "") for entry in release.get("entries", []))

        self.assertIn("#135", entry_text)
        self.assertIn("#20", entry_text)
        self.assertIn("#167", entry_text)
        self.assertIn("gh plate pr babysit", entry_text)
        self.assertIn("plate_epic_status", entry_text)


if __name__ == "__main__":
    unittest.main()
