"""Warn when UI-touching PRs lack valid user-attachments images (#1052)."""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

from plate_core.ci_path_jobs import _path_matches_pattern

WARNING_HEADING = "UI PR visual evidence"

DEFAULT_UI_GLOBS: tuple[str, ...] = (
    "web/**",
    "app/**",
    "src/components/**",
    "public/**",
    "*.css",
    "*.scss",
    "*.tsx",
    "*.jsx",
    "*.vue",
    "*.svelte",
    "*.html",
)

USER_ATTACHMENTS_PREFIX = "https://github.com/user-attachments/assets/"

_VISUAL_EVIDENCE_NA = re.compile(
    r"^Visual evidence:\s*not applicable\s*[—\-]\s*.+",
    re.MULTILINE | re.IGNORECASE,
)
_MD_IMAGE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
_HTML_IMG = re.compile(r"""<img\b[^>]*\ssrc\s*=\s*["']([^"']+)["']""", re.IGNORECASE)


@dataclass(frozen=True)
class UiPrImageCheckResult:
    skipped: bool
    ok: bool
    bad_urls: tuple[str, ...]
    messages: tuple[str, ...]


def default_ui_paths_file() -> Path:
    return Path(".agentic") / "ui-paths.yml"


def load_ui_globs(repo_root: Path | None = None) -> list[str]:
    root = repo_root or Path.cwd()
    config_path = root / default_ui_paths_file()
    if config_path.is_file():
        data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            globs = data.get("globs") or data.get("paths")
            if isinstance(globs, list) and all(isinstance(g, str) for g in globs):
                return [g.strip() for g in globs if g.strip()]
    return list(DEFAULT_UI_GLOBS)


def touches_ui_paths(changed_paths: list[str], globs: list[str] | None = None) -> bool:
    patterns = globs if globs is not None else DEFAULT_UI_GLOBS
    for path in changed_paths:
        normalized = path.strip().replace("\\", "/")
        if not normalized:
            continue
        if any(_path_matches_pattern(pattern, normalized) for pattern in patterns):
            return True
    return False


def visual_evidence_not_applicable(body: str) -> bool:
    return _VISUAL_EVIDENCE_NA.search(body or "") is not None


def extract_image_urls(body: str) -> list[str]:
    text = body or ""
    urls: list[str] = []
    for match in _MD_IMAGE.finditer(text):
        urls.append(match.group(1).strip())
    for match in _HTML_IMG.finditer(text):
        urls.append(match.group(1).strip())
    return urls


def is_valid_user_attachment(url: str) -> bool:
    return url.startswith(USER_ATTACHMENTS_PREFIX)


def classify_bad_image_url(url: str) -> str | None:
    if is_valid_user_attachment(url):
        return None
    lower = url.lower()
    if url.startswith("./") or url.startswith("../") or (
        not lower.startswith("http://") and not lower.startswith("https://")
    ):
        return "relative path"
    if "raw.githubusercontent.com" in lower:
        return "raw.githubusercontent.com URL"
    if "blob/" in lower and "raw=true" in lower:
        return "blob/...?raw=true URL"
    if "github.com" in lower and "/blob/" in lower:
        return "blob URL (use gh pr edit --attach instead)"
    return "non-user-attachments image URL"


def _fix_lines(pr_number: int | None) -> list[str]:
    n = pr_number if pr_number is not None else "N"
    return [
        f"Re-embed screenshots with `gh pr edit {n} --body-file body.md --attach ./shot.png` "
        "(requires gh >= 2.99).",
        "Third-party cloud agents without a user PAT cannot upload attachments — assign the issue "
        "to GitHub Copilot's cloud coding agent (or a human with local `gh` and a PAT) for UI screenshot work.",
    ]


def evaluate_ui_pr_image_check(
    body: str,
    changed_paths: list[str],
    *,
    repo_root: Path | None = None,
    pr_number: int | None = None,
) -> UiPrImageCheckResult:
    globs = load_ui_globs(repo_root)
    if not touches_ui_paths(changed_paths, globs):
        return UiPrImageCheckResult(skipped=True, ok=True, bad_urls=(), messages=())

    if visual_evidence_not_applicable(body):
        return UiPrImageCheckResult(skipped=True, ok=True, bad_urls=(), messages=())

    urls = extract_image_urls(body)
    if any(is_valid_user_attachment(u) for u in urls):
        return UiPrImageCheckResult(skipped=False, ok=True, bad_urls=(), messages=())

    bad: list[str] = []
    for url in urls:
        kind = classify_bad_image_url(url)
        if kind is not None:
            bad.append(url)

    messages: list[str] = [
        "This PR touches UI paths but has no valid `https://github.com/user-attachments/assets/...` images "
        "embedded in the PR description.",
    ]
    if bad:
        messages.append("Invalid image URLs:")
        for url in bad:
            kind = classify_bad_image_url(url) or "invalid"
            messages.append(f"- `{url}` ({kind})")
    elif not urls:
        messages.append("No markdown or HTML images were found in the PR body.")

    messages.extend(_fix_lines(pr_number))
    return UiPrImageCheckResult(skipped=False, ok=False, bad_urls=tuple(bad), messages=tuple(messages))


def _enforce_from_env(cli_enforce: bool) -> bool:
    if cli_enforce:
        return True
    return os.environ.get("PLATE_UI_PR_IMAGE_ENFORCE", "").lower() in {"1", "true", "yes"}


def run_check(
    body: str,
    changed_paths: list[str],
    *,
    repo_root: Path | None = None,
    pr_number: int | None = None,
    enforce: bool = False,
) -> int:
    enforce = _enforce_from_env(enforce)
    result = evaluate_ui_pr_image_check(
        body,
        changed_paths,
        repo_root=repo_root,
        pr_number=pr_number,
    )
    if result.skipped or result.ok:
        return 0
    for msg in result.messages:
        if enforce:
            print(msg, file=sys.stderr)
        else:
            print(f"::warning title={WARNING_HEADING}::{msg}", flush=True)
    if enforce:
        print(f"## ⚠️ {WARNING_HEADING}", file=sys.stderr)
        return 1
    return 0


def _read_paths_file(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Warn when UI-touching PRs lack user-attachments visual evidence (#1052)",
    )
    parser.add_argument("--stdin", action="store_true", help="Read PR body from stdin")
    parser.add_argument("--files", help="Newline-separated list of changed file paths")
    parser.add_argument("--repo-root", default=".", help="Repository root for ui-paths.yml")
    parser.add_argument("--pr-number", type=int, default=None, help="PR number for fix hints")
    parser.add_argument(
        "--enforce",
        action="store_true",
        help="Fail the job instead of emitting warnings (also set PLATE_UI_PR_IMAGE_ENFORCE=1)",
    )
    parser.add_argument("path", nargs="?", help="File containing PR body (alternative to --stdin)")
    args = parser.parse_args(argv)

    enforce = _enforce_from_env(args.enforce)

    if args.stdin:
        body = sys.stdin.read()
    elif args.path:
        body = Path(args.path).read_text(encoding="utf-8")
    else:
        parser.error("provide --stdin or a path argument")

    changed: list[str] = []
    if args.files:
        changed = _read_paths_file(Path(args.files))

    return run_check(
        body,
        changed,
        repo_root=Path(args.repo_root),
        pr_number=args.pr_number,
        enforce=enforce,
    )


if __name__ == "__main__":
    raise SystemExit(main())
