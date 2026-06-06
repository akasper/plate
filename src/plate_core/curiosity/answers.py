"""Answer Model implementation (structured comments + committed storage).

This is the core storage layer for the Curiosity / Q&A Mode vision in Epic #139.
It ensures:
- Never lose user information (append-only provenance)
- Agents can reliably find previous answers (fast local index + committed markdown)
- Users can revisit/revise (history preserved via revision_of links)
- Every answer can drive forward progress (via Contemplation Engine)

Format based on Design #142, while preserving compatibility with the current
PLATE-ANSWER block format already used in this repository.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


PLATE_ANSWER_BEGIN = "<!-- PLATE-ANSWER:BEGIN -->"
PLATE_ANSWER_END = "<!-- PLATE-ANSWER:END -->"

REPO_ROOT = Path(__file__).resolve().parents[3]
DOCS_CURIOSITY_DIR = REPO_ROOT / "docs" / "curiosity"
ANSWERS_DIR = DOCS_CURIOSITY_DIR / "answers"
INDEX_PATH = DOCS_CURIOSITY_DIR / "answers.yml"


def _parse_timestamp(value: str) -> datetime:
    if not value:
        return datetime.min
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return datetime.min


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    return slug or "question"


def _question_answers_relative_path(question_number: int, question_title: str | None) -> str:
    slug = _slugify(question_title or f"question-{question_number}")
    return str(Path("docs") / "curiosity" / "answers" / f"{slug}.md")


def _question_answers_path(question_number: int, question_title: str | None) -> Path:
    return REPO_ROOT / _question_answers_relative_path(question_number, question_title)


@dataclass
class Answer:
    """A single captured answer with full provenance."""

    id: str
    question_number: int
    answered_by: str  # username or agent-id
    timestamp: str  # ISO format
    session: str | None = None
    source: str = "qanda"  # qanda | agent-contemplation | manual | blocking
    answer_text: str = ""
    provenance: dict[str, Any] = field(default_factory=dict)
    agent_actions: list[str] = field(default_factory=list)
    full_comment_url: str | None = None
    revision_of: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "question_number": self.question_number,
            "answered_by": self.answered_by,
            "timestamp": self.timestamp,
            "session": self.session,
            "source": self.source,
            "answer_text": self.answer_text,
            "provenance": self.provenance,
            "agent_actions": self.agent_actions,
            "full_comment_url": self.full_comment_url,
            "revision_of": self.revision_of,
        }


@dataclass
class QuestionAnswers:
    """All known answers for one Question issue."""

    question_number: int
    title: str | None = None
    file_path: str | None = None
    answers: list[Answer] = field(default_factory=list)

    def effective_answers(self) -> list[Answer]:
        superseded = {answer.revision_of for answer in self.answers if answer.revision_of}
        return [answer for answer in self.answers if answer.id not in superseded]

    def latest_answer(self) -> Answer | None:
        candidates = self.effective_answers() or self.answers
        if not candidates:
            return None
        return max(candidates, key=lambda answer: _parse_timestamp(answer.timestamp))

    def to_dict(self) -> dict[str, Any]:
        return {
            "question_number": self.question_number,
            "title": self.title,
            "file_path": self.file_path,
            "answers": [answer.to_dict() for answer in self.answers],
        }


_ANSWER_BLOCK_RE = re.compile(
    rf"{re.escape(PLATE_ANSWER_BEGIN)}(.*?){re.escape(PLATE_ANSWER_END)}",
    re.DOTALL | re.IGNORECASE,
)


def parse_plate_answer_blocks(comment_body: str) -> list[dict[str, str]]:
    """Extract raw PLATE-ANSWER blocks from a comment body."""

    matches = _ANSWER_BLOCK_RE.findall(comment_body or "")
    blocks: list[dict[str, str]] = []
    for raw in matches:
        block: dict[str, str] = {}
        for line in raw.strip().splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                block[key.strip().lower()] = value.strip()
        if block:
            blocks.append(block)
    return blocks


def build_answer_from_block(
    block: dict[str, str],
    question_number: int,
    comment_url: str | None = None,
    answer_id: str | None = None,
) -> Answer:
    """Create an Answer from a parsed PLATE-ANSWER block."""

    timestamp = block.get("timestamp") or datetime.utcnow().isoformat()
    resolved_id = answer_id or block.get("id") or f"ans-{question_number}-{timestamp}"
    revision_of = block.get("revision of") or None
    return Answer(
        id=str(resolved_id),
        question_number=question_number,
        answered_by=block.get("answered by", "unknown"),
        timestamp=timestamp,
        session=block.get("session"),
        source=block.get("source", "manual"),
        answer_text=block.get("answer", ""),
        provenance={"raw_block": block},
        agent_actions=[
            action.strip()
            for action in block.get("agent actions triggered", "").split(";")
            if action.strip()
        ],
        full_comment_url=comment_url,
        revision_of=str(revision_of) if revision_of is not None else None,
    )


def load_answers_index(index_path: Path | None = None) -> dict[int, QuestionAnswers]:
    """Load the committed answers index from disk (if present)."""

    index_path = index_path or INDEX_PATH
    if not index_path.exists():
        return {}
    data = yaml.safe_load(index_path.read_text(encoding="utf-8")) or {}
    index: dict[int, QuestionAnswers] = {}
    for qnum_str, qdata in data.items():
        qnum = int(qnum_str)
        answers = [
            Answer(
                id=str(answer_data.get("id") or f"ans-{qnum}-{position}"),
                question_number=int(answer_data.get("question_number", qnum)),
                answered_by=answer_data.get("answered_by", "unknown"),
                timestamp=answer_data.get("timestamp", ""),
                session=answer_data.get("session"),
                source=answer_data.get("source", "manual"),
                answer_text=answer_data.get("answer_text", ""),
                provenance=answer_data.get("provenance") or {},
                agent_actions=list(answer_data.get("agent_actions") or []),
                full_comment_url=answer_data.get("full_comment_url"),
                revision_of=(
                    str(answer_data.get("revision_of"))
                    if answer_data.get("revision_of") is not None
                    else None
                ),
            )
            for position, answer_data in enumerate(qdata.get("answers", []), start=1)
        ]
        index[qnum] = QuestionAnswers(
            question_number=qnum,
            title=qdata.get("title"),
            file_path=qdata.get("file_path"),
            answers=answers,
        )
    return index


def save_answers_index(
    index: dict[int, QuestionAnswers],
    index_path: Path | None = None,
) -> None:
    """Persist the committed answers index to disk."""

    index_path = index_path or INDEX_PATH
    index_path.parent.mkdir(parents=True, exist_ok=True)
    serializable = {
        str(question_number): {
            "title": question_answers.title,
            "file_path": question_answers.file_path,
            "answers": [answer.to_dict() for answer in question_answers.answers],
        }
        for question_number, question_answers in sorted(index.items())
    }
    index_path.write_text(
        yaml.safe_dump(serializable, sort_keys=True, allow_unicode=True),
        encoding="utf-8",
    )


def _render_question_answers_markdown(question_answers: QuestionAnswers) -> str:
    header = [
        f"# Answers for Question #{question_answers.question_number}",
        "",
        f"**Title:** {question_answers.title or '(unknown)'}",
        f"**Issue:** #{question_answers.question_number}",
        "",
        "This file is generated from committed Answer Model data. GitHub comments remain the source of truth.",
    ]
    latest = question_answers.latest_answer()
    if latest:
        header.extend(
            [
                "",
                f"**Latest effective answer:** {latest.timestamp} by {latest.answered_by}",
            ]
        )
    lines = header

    for position, answer in enumerate(question_answers.answers, start=1):
        lines.extend(
            [
                "",
                f"## Answer {position}",
                "",
                f"- **Answer id:** {answer.id}",
                f"- **Answered by:** {answer.answered_by}",
                f"- **Timestamp:** {answer.timestamp}",
                f"- **Source:** {answer.source}",
            ]
        )
        if answer.session:
            lines.append(f"- **Session:** {answer.session}")
        if answer.revision_of:
            lines.append(f"- **Revision of:** {answer.revision_of}")
        if answer.full_comment_url:
            lines.append(f"- **GitHub comment:** {answer.full_comment_url}")
        if answer.agent_actions:
            lines.append(f"- **Agent actions triggered:** {'; '.join(answer.agent_actions)}")
        lines.extend(
            [
                "",
                "```text",
                answer.answer_text,
                "```",
            ]
        )

    return "\n".join(lines) + "\n"


def write_question_answers_file(
    question_answers: QuestionAnswers,
    answers_dir: Path | None = None,
) -> Path:
    """Write the committed per-question markdown artifact."""

    answers_dir = answers_dir or ANSWERS_DIR
    answers_dir.mkdir(parents=True, exist_ok=True)
    relative_path = Path(
        question_answers.file_path
        or _question_answers_relative_path(question_answers.question_number, question_answers.title)
    )
    path = REPO_ROOT / relative_path if answers_dir == ANSWERS_DIR else answers_dir / relative_path.name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_render_question_answers_markdown(question_answers), encoding="utf-8")
    return path


def update_answers_index(
    question_number: int,
    new_answer: Answer,
    question_title: str | None = None,
    index_path: Path | None = None,
    answers_dir: Path | None = None,
) -> QuestionAnswers:
    """Add an answer to committed storage and keep index + markdown in sync."""

    index_path = index_path or INDEX_PATH
    answers_dir = answers_dir or ANSWERS_DIR
    index = load_answers_index(index_path=index_path)
    if question_number not in index:
        index[question_number] = QuestionAnswers(
            question_number=question_number,
            title=question_title,
            file_path=_question_answers_relative_path(question_number, question_title),
        )

    question_answers = index[question_number]
    if question_title:
        question_answers.title = question_title
    if not question_answers.file_path:
        question_answers.file_path = _question_answers_relative_path(
            question_number,
            question_answers.title,
        )

    existing_ids = {answer.id for answer in question_answers.answers}
    if new_answer.id not in existing_ids:
        question_answers.answers.append(new_answer)
        question_answers.answers.sort(key=lambda answer: _parse_timestamp(answer.timestamp))

    save_answers_index(index, index_path=index_path)
    write_question_answers_file(question_answers, answers_dir=answers_dir)
    return question_answers


def get_answers_for_question(
    question_number: int,
    index_path: Path | None = None,
) -> QuestionAnswers | None:
    """Return all known answers for a Question from committed storage."""

    index_path = index_path or INDEX_PATH
    return load_answers_index(index_path=index_path).get(question_number)


def get_question_answers_path(question_number: int, question_title: str | None) -> Path:
    """Return the committed markdown path for a Question."""

    return _question_answers_path(question_number, question_title)
