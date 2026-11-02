"""PR body gate: author and reviewer models must differ (#1334)."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass

from plate_core.pr_gates_closing import _fence_closer_line, parse_fence_opener

FAILURE_HEADING = "Reviewer model must differ from author model"

_COPILOT_ALIASES = frozenset(
    {
        "copilot",
        "github-copilot",
        "copilot-review",
        "copilot-code-review",
        "copilot-pull-request-reviewer",
    }
)
_CANONICAL_COPILOT_ID = "github-copilot"

_PLACEHOLDER = re.compile(
    r"^(?:tbd|todo|n/a|na|none|—|--|-|\.\.\.|unknown|pending)$",
    re.IGNORECASE,
)

_TABLE_ROW = re.compile(r"^\s*\|(.+)\|\s*$")
_SECTION_HEADING = re.compile(r"^##\s+Agent review models\s*$", re.IGNORECASE)
_NEXT_SECTION = re.compile(r"^##\s+")
_AUTHOR_LABEL = "author model"
_REVIEWER_LABEL = "reviewer model"
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)


@dataclass(frozen=True)
class ReviewModelGateResult:
    ok: bool
    errors: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class ParsedReviewModels:
    author: str | None
    reviewer: str | None
    parse_errors: tuple[str, ...]


def _is_copilot_identity(text: str) -> bool:
    if not text:
        return False
    if text in _COPILOT_ALIASES:
        return True
    return "copilot" in text


def normalize_model_id(raw: str) -> str:
    text = (raw or "").strip().strip("`'\"")
    text = re.sub(r"\s+", "-", text.lower())
    text = re.sub(r"-+", "-", text).strip("-")
    if _is_copilot_identity(text):
        return _CANONICAL_COPILOT_ID
    return text


def model_provider(model_id: str) -> str:
    model = normalize_model_id(model_id)
    if not model:
        return "unknown"
    if model == _CANONICAL_COPILOT_ID:
        return "github-copilot"
    if model in {"human", "human-review", "human-reviewer"} or model.startswith("human-"):
        return "human"
    if "composer" in model or "cursor" in model:
        return "cursor"
    if "claude" in model or "anthropic" in model:
        return "anthropic"
    if "grok" in model or model.startswith("xai"):
        return "xai"
    if "gemini" in model or "bard" in model:
        return "google"
    if "deepseek" in model:
        return "deepseek"
    if "gpt" in model or "openai" in model or "sol" in model:
        return "openai"
    return "unknown"


def _split_table_cells(row: str) -> list[str]:
    parts = [cell.strip() for cell in row.split("|")]
    if parts and parts[0] == "":
        parts = parts[1:]
    if parts and parts[-1] == "":
        parts = parts[:-1]
    return parts


def _normalize_row_label(label: str) -> str:
    text = label.strip()
    text = re.sub(r"[*_`]", "", text)
    return re.sub(r"\s+", " ", text).strip().lower()


def _is_placeholder(value: str) -> bool:
    cleaned = value.strip().strip("`'\"")
    if not cleaned:
        return True
    return bool(_PLACEHOLDER.match(cleaned))


def _row_role(cells: list[str]) -> str | None:
    if len(cells) < 2:
        return None
    label = _normalize_row_label(cells[0])
    if label == _AUTHOR_LABEL:
        return "author"
    if label == _REVIEWER_LABEL:
        return "reviewer"
    return None


def _agent_review_models_section_lines(body: str) -> list[str] | None:
    lines = (body or "").splitlines()
    start: int | None = None
    for index, line in enumerate(lines):
        if _SECTION_HEADING.match(line.strip()):
            start = index + 1
            break
    if start is None:
        return None
    section: list[str] = []
    for line in lines[start:]:
        if _NEXT_SECTION.match(line.strip()):
            break
        section.append(line)
    return section


def _strip_inline_html_comments(line: str) -> str:
    return _HTML_COMMENT.sub("", line)


def parse_review_models_from_body(body: str) -> ParsedReviewModels:
    """Return author/reviewer values from the Agent review models section only."""
    section = _agent_review_models_section_lines(body)
    if section is None:
        return ParsedReviewModels(None, None, ())

    author: str | None = None
    reviewer: str | None = None
    parse_errors: list[str] = []
    in_fence = False
    fence_char = ""
    fence_len = 0

    for raw_line in section:
        bare = raw_line.rstrip("\n\r")
        if in_fence:
            if _fence_closer_line(bare, fence_char, fence_len):
                in_fence = False
                fence_char = ""
                fence_len = 0
            continue
        opener = parse_fence_opener(bare)
        if opener:
            fence_char, fence_len = opener
            in_fence = True
            continue

        line = _strip_inline_html_comments(bare)
        match = _TABLE_ROW.match(line)
        if not match:
            continue
        cells = _split_table_cells(match.group(1))
        role = _row_role(cells)
        if role == "author":
            if author is not None:
                parse_errors.append("Duplicate **Author model** row in Agent review models table.")
            author = cells[1]
        elif role == "reviewer":
            if reviewer is not None:
                parse_errors.append("Duplicate **Reviewer model** row in Agent review models table.")
            reviewer = cells[1]

    return ParsedReviewModels(author, reviewer, tuple(parse_errors))


def evaluate_review_model_gate(
    author_raw: str | None,
    reviewer_raw: str | None,
    *,
    parse_errors: tuple[str, ...] = (),
) -> ReviewModelGateResult:
    errors: list[str] = list(parse_errors)
    warnings: list[str] = []

    if author_raw is None or _is_placeholder(author_raw):
        errors.append(
            "Add an **Author model** row under **Agent review models** in the PR body "
            "(implementation agent model id, or `human` for human-only work)."
        )
    if reviewer_raw is None or _is_placeholder(reviewer_raw):
        errors.append(
            "Add a **Reviewer model** row under **Agent review models**. "
            "GitHub Copilot code review is allowed — use `copilot` as the reviewer model."
        )

    if errors:
        return ReviewModelGateResult(ok=False, errors=tuple(errors), warnings=tuple(warnings))

    author_norm = normalize_model_id(author_raw or "")
    reviewer_norm = normalize_model_id(reviewer_raw or "")

    if author_norm == reviewer_norm:
        errors.append(
            f"Author model and reviewer model must differ (both recorded as `{author_norm}`). "
            "Pick a different reviewer model (for example `copilot` or another agent model)."
        )

    author_provider = model_provider(author_norm)
    reviewer_provider = model_provider(reviewer_norm)
    if (
        author_provider != "unknown"
        and reviewer_provider != "unknown"
        and author_provider == reviewer_provider
        and author_norm != reviewer_norm
    ):
        warnings.append(
            f"Author and reviewer share provider `{author_provider}` "
            f"(`{author_norm}` vs `{reviewer_norm}`). Prefer a different provider when possible."
        )

    return ReviewModelGateResult(
        ok=not errors,
        errors=tuple(errors),
        warnings=tuple(warnings),
    )


def evaluate_review_model_gate_from_body(body: str) -> ReviewModelGateResult:
    parsed = parse_review_models_from_body(body)
    return evaluate_review_model_gate(
        parsed.author,
        parsed.reviewer,
        parse_errors=parsed.parse_errors,
    )


def format_failure_message(result: ReviewModelGateResult) -> str:
    lines = [
        f"## ⚠️ {FAILURE_HEADING}",
        "",
        "Record author and reviewer models in the **Agent review models** table. "
        "Human merge approval is unchanged; this gate only blocks same-model self-review.",
        "",
    ]
    for err in result.errors:
        lines.append(f"- {err}")
    return "\n".join(lines)


def run_gate(body: str, *, enforce: bool = False) -> int:
    """Return 0 unless ``enforce`` is true and the table fails.

    Warn-only by default (first release): problems are printed as GitHub warnings so
    adopters can add the table before the check starts blocking.
    """
    result = evaluate_review_model_gate_from_body(body)
    for warning in result.warnings:
        print(f"::warning title=Reviewer model::{warning}", flush=True)
    if result.ok:
        return 0
    if not enforce:
        for err in result.errors:
            print(f"::warning title=Reviewer model (warn-only)::{err}", flush=True)
        return 0
    print(format_failure_message(result), file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate PR author/reviewer model fields (#1334)")
    parser.add_argument(
        "--stdin",
        action="store_true",
        help="Read PR body from standard input",
    )
    parser.add_argument(
        "--enforce",
        action="store_true",
        help="Exit non-zero when the table is missing or author equals reviewer (default: warn only)",
    )
    parser.add_argument(
        "path",
        nargs="?",
        help="Path to a file containing the PR body",
    )
    args = parser.parse_args(argv)
    if args.stdin:
        body = sys.stdin.read()
    elif args.path:
        body = open(args.path, encoding="utf-8").read()
    else:
        parser.error("provide --stdin or a path argument")
    return run_gate(body, enforce=args.enforce)


if __name__ == "__main__":
    raise SystemExit(main())
