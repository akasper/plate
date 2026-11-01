import unittest
from pathlib import Path

from plate_core.github_labels import (
    GITHUB_LABEL_DESCRIPTION_MAX_LENGTH,
    find_overlong_shipped_label_descriptions,
    prepare_label_description,
    registry_label_case_mismatches,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


class GitHubLabelDescriptionTests(unittest.TestCase):
    def test_shipped_labels_yml_descriptions_within_github_limit(self):
        violations = find_overlong_shipped_label_descriptions(REPO_ROOT)
        self.assertEqual(
            [],
            violations,
            msg="Label descriptions must be <= "
            f"{GITHUB_LABEL_DESCRIPTION_MAX_LENGTH} characters: {violations}",
        )

    def test_prepare_label_description_truncates_with_warning(self):
        long_desc = "x" * (GITHUB_LABEL_DESCRIPTION_MAX_LENGTH + 5)
        prepared, warning = prepare_label_description(long_desc)
        self.assertEqual(GITHUB_LABEL_DESCRIPTION_MAX_LENGTH, len(prepared))
        self.assertIsNotNone(warning)
        self.assertIn(str(GITHUB_LABEL_DESCRIPTION_MAX_LENGTH), warning)

    def test_prepare_label_description_passes_short_text(self):
        short = "Short label description."
        prepared, warning = prepare_label_description(short)
        self.assertEqual(short, prepared)
        self.assertIsNone(warning)

    def test_registry_label_case_mismatches_detects_github_defaults(self):
        messages = registry_label_case_mismatches(
            ["Bug", "Documentation"],
            [
                {"name": "bug", "color": "d73a4a", "description": ""},
                {"name": "documentation", "color": "0075ca", "description": ""},
            ],
        )
        self.assertEqual(
            messages,
            ["`bug` should be `Bug`", "`documentation` should be `Documentation`"],
        )
        self.assertEqual(
            registry_label_case_mismatches(
                ["Bug"],
                [{"name": "Bug", "color": "d73a4a", "description": ""}],
            ),
            [],
        )


if __name__ == "__main__":
    unittest.main()
