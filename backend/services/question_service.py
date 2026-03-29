"""
services/question_service.py — Parse uploaded question bank files.
Supports CSV, JSON, TXT and DOCX.

CSV expected columns (case-insensitive):
    question / text  (required)
    topic            (optional)
    difficulty       (optional)
    keywords         (optional, pipe-separated)

JSON expected shape:
    { "name": "...", "role": "...", "questions": [ { "text": "...", ... } ] }
    — OR —
    [ { "text": "...", ... }, ... ]
"""

from __future__ import annotations
import csv
import io
import json
from typing import Any

from docx import Document

from models.schemas import Question, QuestionBank


# ── Internal helpers ──────────────────────────────────────────────────────────

def _normalise_header(h: str) -> str:
    return h.strip().lower().replace(" ", "_")


def _parse_keywords(raw: str) -> list[str]:
    """Split pipe- or comma-separated keyword strings."""
    if not raw:
        return []
    sep = "|" if "|" in raw else ","
    return [k.strip() for k in raw.split(sep) if k.strip()]


def _row_to_question(row: dict[str, str]) -> Question:
    normalised = {_normalise_header(k): v for k, v in row.items()}
    text = normalised.get("question") or normalised.get("text", "")
    if not text:
        raise ValueError(f"Row missing required 'question'/'text' field: {row}")
    return Question(
        text=text.strip(),
        topic=normalised.get("topic", "").strip() or None,
        difficulty=normalised.get("difficulty", "").strip() or None,
        expected_keywords=_parse_keywords(normalised.get("keywords", "")),
    )


# ── Public parsers ────────────────────────────────────────────────────────────

def parse_csv(content: bytes, bank_name: str, role: str | None = None) -> QuestionBank:
    """Parse CSV bytes into a QuestionBank."""
    reader = csv.DictReader(io.StringIO(content.decode("utf-8")))
    questions: list[Question] = []

    for row in reader:
        try:
            questions.append(_row_to_question(row))
        except ValueError:
            continue

    if not questions:
        raise ValueError("CSV contained no valid questions.")

    return QuestionBank(name=bank_name, role=role, questions=questions)


def parse_json(content: bytes, bank_name: str, role: str | None = None) -> QuestionBank:
    """Parse JSON bytes into a QuestionBank."""

    data: Any = json.loads(content.decode("utf-8"))

    if isinstance(data, list):
        raw_questions = data
        name = bank_name

    elif isinstance(data, dict):
        raw_questions = data.get("questions", [])
        name = data.get("name", bank_name)
        role = data.get("role", role)

    else:
        raise ValueError("JSON must be an array or object with a 'questions' key.")

    questions: list[Question] = []

    for item in raw_questions:

        text = item.get("text") or item.get("question", "")

        if not text:
            continue

        questions.append(
            Question(
                text=text.strip(),
                topic=item.get("topic") or None,
                difficulty=item.get("difficulty") or None,
                expected_keywords=_parse_keywords(item.get("keywords", "")),
            )
        )

    if not questions:
        raise ValueError("JSON contained no valid questions.")

    return QuestionBank(name=name, role=role, questions=questions)


def parse_txt(content: bytes, bank_name: str, role: str | None = None) -> QuestionBank:
    """Parse TXT where each line is a question."""

    text = content.decode("utf-8")

    questions: list[Question] = []

    for line in text.splitlines():

        line = line.strip()

        if not line:
            continue

        questions.append(
            Question(
                text=line,
                topic=None,
                difficulty=None,
                expected_keywords=[]
            )
        )

    if not questions:
        raise ValueError("TXT contained no valid questions.")

    return QuestionBank(name=bank_name, role=role, questions=questions)


def parse_docx(content: bytes, bank_name: str, role: str | None = None) -> QuestionBank:
    """Parse DOCX where each paragraph is a question."""

    doc = Document(io.BytesIO(content))

    questions: list[Question] = []

    for para in doc.paragraphs:

        text = para.text.strip()

        if not text:
            continue

        questions.append(
            Question(
                text=text,
                topic=None,
                difficulty=None,
                expected_keywords=[]
            )
        )

    if not questions:
        raise ValueError("DOCX contained no valid questions.")

    return QuestionBank(name=bank_name, role=role, questions=questions)


# ── Dispatcher ────────────────────────────────────────────────────────────────

def parse_question_bank(
    content: bytes,
    filename: str,
    bank_name: str,
    role: str | None = None,
) -> QuestionBank:

    """Route to the correct parser based on file extension."""

    ext = filename.rsplit(".", 1)[-1].lower()

    if ext == "csv":
        return parse_csv(content, bank_name, role)

    elif ext in ("json", "jsonl"):
        return parse_json(content, bank_name, role)

    elif ext == "txt":
        return parse_txt(content, bank_name, role)

    elif ext in ("docx", "doc"):
        return parse_docx(content, bank_name, role)

    else:
        raise ValueError(
            f"Unsupported file type: .{ext}. Use .csv, .json, .txt or .docx"
        )