"""Acceptance tests for UI PR image check (#1052)."""

import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from plate_core.ci_path_jobs import path_matches_pattern
from plate_core.pr_ui_pr_image_check import (
    USER_ATTACHMENTS_PREFIX,
    DEFAULT_UI_GLOBS,
    classify_bad_image_url,
    evaluate_ui_pr_image_check,
    extract_image_urls,
    load_ui_globs,
    run_check,
    touches_ui_paths,
    visual_evidence_not_applicable,
)


class UiPathGlobTests(unittest.TestCase):
    def test_default_globs_when_config_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            globs = load_ui_globs(Path(tmp))
            self.assertEqual(globs, list(DEFAULT_UI_GLOBS))

    def test_loads_globs_from_ui_paths_yml(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agentic = root / ".agentic"
            agentic.mkdir()
            (agentic / "ui-paths.yml").write_text(
                "globs:\n  - custom-ui/**\n  - '*.tsx'\n",
                encoding="utf-8",
            )
            self.assertEqual(load_ui_globs(root), ["custom-ui/**", "*.tsx"])

    def test_touches_ui_path_by_glob(self):
        self.assertTrue(touches_ui_paths(["src/components/Button.tsx"]))
        self.assertTrue(touches_ui_paths(["web/index.html"]))
        self.assertFalse(touches_ui_paths(["src/plate_core/cli.py"]))

    def test_no_ui_changes_never_flagged(self):
        result = evaluate_ui_pr_image_check("no images", ["README.md", "src/plate_core/x.py"])
        self.assertTrue(result.skipped)
        self.assertTrue(result.ok)

    def test_public_path_matches_pattern(self):
        self.assertTrue(path_matches_pattern("*.tsx", "src/components/App.tsx"))
        self.assertFalse(path_matches_pattern("*.tsx", "src/plate_core/cli.py"))


class VisualEvidenceEscapeTests(unittest.TestCase):
    def test_escape_hatch_skips_check(self):
        body = "Visual evidence: not applicable — internal refactor only"
        result = evaluate_ui_pr_image_check(body, ["src/components/x.tsx"])
        self.assertTrue(result.skipped)
        self.assertTrue(result.ok)

    def test_escape_hatch_detector(self):
        self.assertTrue(visual_evidence_not_applicable("Visual evidence: not applicable — reason"))
        self.assertFalse(visual_evidence_not_applicable("Visual evidence: attached below"))


class ImageUrlTests(unittest.TestCase):
    def test_valid_user_attachment_passes(self):
        url = f"{USER_ATTACHMENTS_PREFIX}abc-123"
        body = f"![desktop]({url})"
        result = evaluate_ui_pr_image_check(body, ["app/page.tsx"])
        self.assertTrue(result.ok)
        self.assertFalse(result.skipped)

    def test_warns_with_no_images_on_ui_pr(self):
        result = evaluate_ui_pr_image_check("## Summary\nText only.", ["public/logo.svg"])
        self.assertFalse(result.ok)
        self.assertIn("user-attachments", result.messages[0])
        self.assertIn("gh pr edit", " ".join(result.messages))

    def test_warns_and_names_bad_urls(self):
        body = "\n".join(
            [
                "![rel](./screens/desktop.png)",
                "![raw](https://raw.githubusercontent.com/o/r/main/shot.png)",
                "![blob](https://github.com/o/r/blob/main/x.png?raw=true)",
            ]
        )
        result = evaluate_ui_pr_image_check(body, ["src/components/App.tsx"], pr_number=42)
        self.assertFalse(result.ok)
        self.assertEqual(len(result.bad_urls), 3)
        joined = "\n".join(result.messages)
        self.assertIn("./screens/desktop.png", joined)
        self.assertIn("raw.githubusercontent.com", joined)
        self.assertIn("blob/", joined)
        self.assertIn("Copilot", joined)
        self.assertIn("gh pr edit 42", joined)

    def test_classify_bad_urls(self):
        self.assertIsNone(classify_bad_image_url(f"{USER_ATTACHMENTS_PREFIX}x"))
        self.assertEqual(classify_bad_image_url("./a.png"), "relative path")
        self.assertIn("raw", classify_bad_image_url("https://raw.githubusercontent.com/a/b/c.png") or "")
        self.assertIsNone(classify_bad_image_url("https://github.com/o/r/blob/main/x.png"))
        self.assertIsNotNone(
            classify_bad_image_url("https://github.com/o/r/blob/main/x.png?raw=true")
        )

    def test_extract_markdown_and_html_images(self):
        body = "![a](https://x.test/1.png) and <img src='./b.png' /> and <img src=./c.png>"
        urls = extract_image_urls(body)
        self.assertEqual(urls, ["https://x.test/1.png", "./b.png", "./c.png"])


class EnforceModeTests(unittest.TestCase):
    def test_warn_mode_never_exits_nonzero(self):
        sink = io.StringIO()
        with redirect_stdout(sink):
            code = run_check("no images", ["app/x.css"], enforce=False, pr_number=9)
        self.assertEqual(code, 0)
        self.assertIn("::warning title=UI PR visual evidence::", sink.getvalue())

    def test_no_ui_glob_changes_emit_no_warning(self):
        sink = io.StringIO()
        with redirect_stdout(sink):
            code = run_check("no images", ["README.md"], enforce=False)
        self.assertEqual(code, 0)
        self.assertEqual(sink.getvalue(), "")

    def test_fail_mode_exits_nonzero_without_valid_image(self):
        with mock.patch("sys.stderr", new_callable=io.StringIO) as err:
            with redirect_stdout(io.StringIO()):
                code = run_check("no images", ["app/x.css"], enforce=True, pr_number=3)
        self.assertEqual(code, 1)
        self.assertIn("gh pr edit 3", err.getvalue())

    def test_env_enforce_honored_via_main(self):
        from plate_core.pr_ui_pr_image_check import main

        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as body_file:
            body_file.write("no images")
            body_path = body_file.name
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as files_file:
            files_file.write("app/x.css\n")
            files_path = files_file.name
        try:
            with mock.patch.dict(os.environ, {"PLATE_UI_PR_IMAGE_ENFORCE": "1"}):
                with mock.patch("sys.stderr", new_callable=io.StringIO):
                    with redirect_stdout(io.StringIO()):
                        code = main(
                            [
                                body_path,
                                "--files",
                                files_path,
                                "--pr-number",
                                "7",
                            ]
                        )
        finally:
            Path(body_path).unlink(missing_ok=True)
            Path(files_path).unlink(missing_ok=True)
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
