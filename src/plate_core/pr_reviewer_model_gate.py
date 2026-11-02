"""PR body gate: author and reviewer models must differ (#1334)."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass

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

_PLACEHOLDER = re.compile(
    r"^(?:tbd|todo|n/a|na|none|—|--|-|\.\.\.|unknown|pending)$",
    re.IGNORECASE,
)

_TABLE_ROW = re.compile(r"^\s*\|(.+)\|\s*$")


@dataclass(frozen=True)
class ReviewModelGateResult:
    ok: bool
    errors: tuple[str, ...]
    warnings: tuple[str, ...]


def normalize_model_id(raw: str) -> str:
    text = (raw or "").strip().strip("`'\"")
    text = re.sub(r"\s+", "-", text.lower())
    text = re.sub(r"-+", "-", text).strip("-")
    return text


def model_provider(model_id: str) -> str:
    model = normalize_model_id(model_id)
    if not model:
        return "unknown"
    if model in _COPILOT_ALIASES or "copilot" in model:
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


def _is_placeholder(value: str) -> bool:
    cleaned = value.strip().strip("`'\"")
    if not cleaned:
        return True
    return bool(_PLACEHOLDER.match(cleaned))


def _row_role(cells: list[str]) -> str | None:
    if len(cells) < 2:
        return None
    label = cells[0].lower()
    if "author" in label and "reviewer" not in label:
        return "author"
    if "reviewer" in label:
        return "reviewer"
    return None


def parse_review_models_from_body(body: str) -> tuple[str | None, str | None]:
    """Return (author_model, reviewer_model) raw cell values from the PR body table."""
    author: str | None = None
    reviewer: str | None = None
    for line in (body or "").splitlines():
        match = _TABLE_ROW.match(line)
        if not match:
            continue
        cells = _split_table_cells(match.group(1))
        role = _row_role(cells)
        if role == "author":
            author = cells[1]
        elif role == "reviewer":
            reviewer = cells[1]
    return author, reviewer


def evaluate_review_model_gate(
    author_raw: str | None,
    reviewer_raw: str | None,
) -> ReviewModelGateResult:
    errors: list[str] = []
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
    author, reviewer = parse_review_models_from_body(body)
    return evaluate_review_model_gate(author, reviewer)


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


def run_gate(body: str) -> int:
    result = evaluate_review_model_gate_from_body(body)
    for warning in result.warnings:
        print(f"::warning title=Reviewer model::{warning}", flush=True)
    if result.ok:
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
    return run_gate(body)


if __name__ == "__main__":
    raise SystemExit(main())
