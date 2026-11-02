import unittest

from plate_core.pr_reviewer_model_gate import (
    FAILURE_HEADING,
    evaluate_review_model_gate,
    evaluate_review_model_gate_from_body,
    model_provider,
    normalize_model_id,
    parse_review_models_from_body,
    run_gate,
)


class ReviewModelNormalizeTests(unittest.TestCase):
    def test_normalize_strips_and_lowercases(self):
        self.assertEqual(normalize_model_id("  Cursor-Grok-4.6-High  "), "cursor-grok-4.6-high")
        self.assertEqual(normalize_model_id("`copilot`"), "copilot")

    def test_copilot_provider(self):
        self.assertEqual(model_provider("copilot"), "github-copilot")
        self.assertEqual(model_provider("GitHub Copilot review"), "github-copilot")

    def test_distinct_providers(self):
        self.assertEqual(model_provider("cursor-grok-4.6-high"), "cursor")
        self.assertEqual(model_provider("claude-sonnet-4"), "anthropic")


class ReviewModelGateTests(unittest.TestCase):
    def test_missing_fields_fail(self):
        result = evaluate_review_model_gate(None, "copilot")
        self.assertFalse(result.ok)
        self.assertTrue(any("Author model" in e for e in result.errors))

    def test_same_model_fails(self):
        result = evaluate_review_model_gate("cursor-grok-4.6-high", "cursor-grok-4.6-high")
        self.assertFalse(result.ok)
        self.assertTrue(any("must differ" in e for e in result.errors))

    def test_copilot_reviewer_allowed(self):
        result = evaluate_review_model_gate("cursor-grok-4.6-high", "copilot")
        self.assertTrue(result.ok)
        self.assertEqual(result.warnings, ())

    def test_shared_provider_warns(self):
        result = evaluate_review_model_gate("gpt-5.6-sol-high", "gpt-5.6-sol-low")
        self.assertTrue(result.ok)
        self.assertEqual(len(result.warnings), 1)
        self.assertIn("openai", result.warnings[0])

    def test_parse_table_from_body(self):
        body = """
## Agent review models

| Role | Model |
|---|---|
| Author model | cursor-grok-4.6-high |
| Reviewer model | copilot |
"""
        author, reviewer = parse_review_models_from_body(body)
        self.assertEqual(author, "cursor-grok-4.6-high")
        self.assertEqual(reviewer, "copilot")
        self.assertTrue(evaluate_review_model_gate_from_body(body).ok)

    def test_run_gate_exit_codes(self):
        ok_body = "| Author model | human |\n| Reviewer model | copilot |\n"
        self.assertEqual(run_gate(ok_body), 0)
        bad_body = "| Author model | grok |\n| Reviewer model | grok |\n"
        # Warn-only by default; blocking only with enforce=True.
        self.assertEqual(run_gate(bad_body), 0)
        self.assertEqual(run_gate(bad_body, enforce=True), 1)
        self.assertEqual(run_gate("no table here", enforce=True), 1)
        self.assertEqual(run_gate("no table here"), 0)

    def test_failure_heading_constant(self):
        self.assertIn("differ", FAILURE_HEADING.lower())


if __name__ == "__main__":
    unittest.main()
