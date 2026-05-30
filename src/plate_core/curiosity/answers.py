"""Answer Model implementation (structured comments + committed index).

This is the core storage layer for the Curiosity / Q&A Mode vision in Epic #139.
It ensures:
- Never lose user information (append-only provenance)
- Agents can reliably find previous answers (fast index + GitHub links)
- Users can revisit/revise (history preserved)
- Every answer drives forward progress (via Contemplation Engine)

Format based on Design #142.
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


@dataclass
class Answer:
    """A single captured answer with full provenance."""
    id: str
    question_number: int
    answered_by: str  # username or agent-id
    timestamp: str  # ISO format
    session: str | None = None
    source: str = "qanda"  # /qanda | agent-contemplation | manual | blocking
    answer_text: str = ""
    provenance: dict[str, Any] = field(default_factory=dict)
    agent_actions: list[str] = field(default_factory=list)  # e.g. "Created: #146"
    full_comment_url: str | None = None  # link back to the GitHub comment

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
        }


@dataclass
class QuestionAnswers:
    """All known answers for one Question issue."""
    question_number: int
    title: str | None = None
    answers: list[Answer] = field(default_factory=list)

    def latest_answer(self) -> Answer | None:
        if not self.answers:
            return None
        return max(self.answers, key=lambda a: a.timestamp)

    def to_dict(self) -> dict[str, Any]:
        return {
            "question_number": self.question_number,
            "title": self.title,
            "answers": [a.to_dict() for a in self.answers],
        }


# Regex to extract the PLATE-ANSWER block
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
    block: dict[str, str], question_number: int, comment_url: str | None = None
) -> Answer:
    """Create an Answer from a parsed PLATE-ANSWER block."""
    now = datetime.utcnow().isoformat()
    return Answer(
        id=block.get("id", f"ans-{question_number}-{now}"),
        question_number=question_number,
        answered_by=block.get("answered by", "unknown"),
        timestamp=block.get("timestamp", now),
        session=block.get("session"),
        source=block.get("source", "manual"),
        answer_text=block.get("answer", ""),
        provenance={"raw_block": block},
        agent_actions=[
            a.strip() for a in block.get("agent actions triggered", "").split(";") if a.strip()
        ],
        full_comment_url=comment_url,
    )


# --- Committed index handling (docs/curiosity/answers.yml) ---

INDEX_PATH = Path("docs/curiosity/answers.yml")


def load_answers_index() -> dict[int, QuestionAnswers]:
    """Load the committed answers index from disk (if present)."""
    if not INDEX_PATH.exists():
        return {}
    data = yaml.safe_load(INDEX_PATH.read_text(encoding="utf-8")) or {}
    index: dict[int, QuestionAnswers] = {}
    for qnum_str, qdata in data.items():
        qnum = int(qnum_str)
        answers = [
            Answer(**a) for a in qdata.get("answers", [])
        ]
        index[qnum] = QuestionAnswers(
            question_number=qnum,
            title=qdata.get("title"),
            answers=answers,
        )
    return index


def save_answers_index(index: dict[int, QuestionAnswers]) -> None:
    """Persist the index to docs/curiosity/answers.yml."""
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    serializable = {
        str(qnum): {
            "title": qa.title,
            "answers": [a.to_dict() for a in qa.answers],
        }
        for qnum, qa in index.items()
    }
    INDEX_PATH.write_text(
        yaml.safe_dump(serializable, sort_keys=True, allow_unicode=True),
        encoding="utf-8",
    )


def update_answers_index(
    question_number: int,
    new_answer: Answer,
    question_title: str | None = None,
) -> QuestionAnswers:
    """Add an answer to the in-memory + on-disk index."""
    index = load_answers_index()
    if question_number not in index:
        index[question_number] = QuestionAnswers(
            question_number=question_number, title=question_title
        )
    qa = index[question_number]
    if question_title:
        qa.title = question_title
    qa.answers.append(new_answer)
    save_answers_index(index)
    return qa


def get_answers_for_question(question_number: int) -> QuestionAnswers | None:
    """Return all known answers for a Question (from the fast index)."""
    return load_answers_index().get(question_number)
