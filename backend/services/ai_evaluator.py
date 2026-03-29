"""
services/ai_evaluator.py — Evaluation via OpenRouter (httpx, async).

Fixes applied:
  * Fallback model list no longer includes broken deepseek-r1:free
  * Recommendation field forced to standard values via schema hint in prompt
  * Better JSON schema enforcement — less likely to return markdown-wrapped JSON
  * Timeout increased to 120s for slow free-tier models
"""

from __future__ import annotations
import json
import logging
from typing import Any

import httpx

from config import settings
from models.schemas import (
    AnswerEntry,
    CommunicationAssessment,
    EvalRating,
    EvaluationReport,
    QuestionEvaluation,
    Session,
)

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are a senior technical recruiter and talent evaluation expert with 15+ years of experience.
Your task is to deeply evaluate candidate interview responses and produce a structured JSON report.

SCORING RUBRIC (0-100):
  90-100: Exceptional — mastery demonstrated, specific examples, structured thinking
  75-89:  Good — solid understanding, clear reasoning, minor gaps
  55-74:  Average — basic competency shown, lacks depth or precision
  30-54:  Weak — significant knowledge gaps, unclear thinking
  0-29:   Very Weak — completely off-topic, incoherent, or skipped
  IMPORTANT: Answers of "(skipped — no response)" OR under 5 meaningful words → score 0.

RULES:
  - Return ONLY a valid JSON object. No markdown, no code fences, no preamble.
  - "recommendation" MUST be exactly one of: "Strong Hire", "Hire", "Consider", "No Hire"
  - "overall_rating" MUST be exactly one of: "strong", "good", "average", "weak"
  - "rating" per question MUST be exactly one of: "strong", "good", "average", "weak"
  - question_evaluations array MUST have exactly one item per question, in order.

JSON SCHEMA:
{
  "summary": "2-3 sentence overview of candidate performance",
  "executive_summary": "Detailed paragraph: technical depth, communication, role fitness",
  "overall_score": <integer 0-100>,
  "overall_rating": "good",
  "recommendation": "Hire",
  "strengths": ["specific strength 1", "specific strength 2"],
  "improvements": ["specific gap 1"],
  "hiring_notes": "Private notes for internal review — be candid",
  "risk_flags": [],
  "question_evaluations": [
    {
      "score": <integer 0-100>,
      "rating": "good",
      "strengths": ["what was good"],
      "improvements": ["what was missing"],
      "feedback": "Short direct feedback for the candidate (1-2 sentences)",
      "detailed_feedback": "In-depth 2-3 paragraph analysis of accuracy, depth, communication",
      "keywords_hit": ["relevant", "keywords", "mentioned"],
      "was_skipped": false,
      "communication": {
        "clarity": <0-10>,
        "confidence": <0-10>,
        "depth": <0-10>,
        "relevance": <0-10>
      }
    }
  ]
}"""


def _build_user_prompt(session: Session, answers: list[AnswerEntry], bank=None) -> str:
    lines = [
        f"CANDIDATE: {session.candidate_name}",
        f"ROLE APPLIED FOR: {session.candidate_role or 'Not specified'}",
        f"TOTAL QUESTIONS: {len(answers)}",
        "",
        "=" * 60,
        "INTERVIEW TRANSCRIPT",
        "=" * 60,
    ]

    keyword_map = {}
    if bank and bank.questions:
        keyword_map = {q.id: q.expected_keywords for q in bank.questions}

    for i, entry in enumerate(answers, 1):
        skipped = entry.was_skipped or entry.answer_transcript.strip() in [
            "(skipped — no response)", "(No answer provided)", "",
        ]
        expected_kw = keyword_map.get(entry.question_id, [])
        lines += [
            f"\n[QUESTION {i}]",
            f"Topic: {entry.topic or 'General'}",
            f"Question: {entry.question_text}",
            f"Expected Keywords: {', '.join(expected_kw) if expected_kw else 'None specified'}",
            f"Candidate Answer: {entry.answer_transcript if not skipped else '(skipped — no response)'}",
        ]

    lines += [
        "",
        "=" * 60,
        "Evaluate all questions above. Return ONLY the JSON object.",
        "=" * 60,
    ]
    return "\n".join(lines)


def _score_to_rating(score: int) -> EvalRating:
    if score >= 90:
        return EvalRating.STRONG
    if score >= 75:
        return EvalRating.GOOD
    if score >= 55:
        return EvalRating.AVERAGE
    return EvalRating.WEAK


def _recommendation_from_score(score: int) -> str:
    if score >= 88:
        return "Strong Hire"
    if score >= 75:
        return "Hire"
    if score >= 60:
        return "Consider"
    return "No Hire"


def _fallback_evaluation(session: Session, answers: list[AnswerEntry]) -> dict[str, Any]:
    evals = []
    for entry in answers:
        skipped = entry.was_skipped or not entry.answer_transcript.strip()
        word_count = len(entry.answer_transcript.split())
        score = 0 if skipped else min(100, max(30, 40 + word_count * 0.8))
        evals.append({
            "score": int(score),
            "rating": _score_to_rating(int(score)).value,
            "strengths": [] if skipped else ["Response recorded"],
            "improvements": ["Configure LLM_API_KEY in .env for AI-powered evaluation"],
            "feedback": "Skipped." if skipped else "Response recorded — AI evaluation unavailable.",
            "detailed_feedback": "AI evaluation is not configured. Set LLM_API_KEY in your .env file.",
            "keywords_hit": [],
            "communication": {"clarity": 0, "confidence": 0, "depth": 0, "relevance": 0},
            "was_skipped": skipped,
        })
    overall = int(sum(e["score"] for e in evals) / len(evals)) if evals else 0
    return {
        "question_evaluations": evals,
        "overall_score": overall,
        "overall_rating": _score_to_rating(overall).value,
        "summary": "AI evaluation unavailable — LLM_API_KEY not set in .env",
        "executive_summary": "AI evaluation unavailable. Please set LLM_API_KEY in your .env file.",
        "strengths": ["Candidate completed the interview"],
        "improvements": ["Set LLM_API_KEY in .env to enable AI-powered evaluation"],
        "recommendation": _recommendation_from_score(overall),
        "hiring_notes": "AI evaluation not configured.",
        "risk_flags": ["AI evaluation unavailable — scores are word-count estimates only"],
    }


async def _call_openrouter(user_prompt: str, model: str) -> str:
    """Call OpenRouter API with given model. Raises on HTTP/network errors."""
    logger.info("Calling OpenRouter model: %s", model)
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"{settings.openrouter_base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.llm_api_key}",
                "HTTP-Referer": settings.openrouter_site_url,
                "X-Title": settings.openrouter_site_name,
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                "max_tokens": 6000,
                "temperature": 0.2,
                "response_format": {"type": "json_object"},
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()


def _parse_llm_response(text: str) -> dict[str, Any]:
    logger.info("Parsing LLM response (%d chars)", len(text))
    try:
        # Strip markdown code fences if present
        if "```" in text:
            parts = text.split("```")
            for part in parts:
                part = part.strip()
                if part.startswith("json"):
                    part = part[4:].strip()
                if part.startswith("{"):
                    text = part
                    break

        start = text.find("{")
        end = text.rfind("}") + 1
        if start == -1 or end <= start:
            raise ValueError("No JSON object found in LLM response")

        result = json.loads(text[start:end])
        logger.info("LLM response parsed successfully: %d keys", len(result))
        return result
    except json.JSONDecodeError as exc:
        logger.error("JSON parse error: %s | Raw snippet: '%s'", exc, text[:300])
        raise ValueError(f"Failed to parse LLM evaluation JSON: {exc}") from exc


async def evaluate_session(session: Session) -> EvaluationReport:
    answers = session.answers
    if not answers:
        raise ValueError("Session has no answers to evaluate.")

    from services.session_store import store as _store
    bank = _store.get_bank(session.bank_id)

    raw: dict[str, Any] = {}

    if not settings.llm_api_key:
        logger.warning("LLM_API_KEY not set — using fallback evaluator.")
        raw = _fallback_evaluation(session, answers)
    else:
        user_prompt = _build_user_prompt(session, answers, bank=bank)
        logger.info("Prompt length: %s characters", len(user_prompt))

        # Build model list: primary first, then fallbacks (deduplicated)
        models_to_try = [settings.llm_model] + [
            m for m in settings.llm_fallback_models if m != settings.llm_model
        ]

        last_error = None
        for model in models_to_try:
            try:
                logger.info("Trying model: %s", model)
                text = await _call_openrouter(user_prompt, model)
                logger.info("Raw LLM response received")
                raw = _parse_llm_response(text)
                logger.info("Evaluation succeeded with model: %s", model)
                break
            except Exception as e:
                last_error = e
                logger.warning("Model %s failed: %s", model, e)

        if not raw:
            logger.error("All models failed. Last error: %s. Using fallback.", last_error)
            raw = _fallback_evaluation(session, answers)

    # ── Build structured report ───────────────────────────────────────────────
    q_evals: list[QuestionEvaluation] = []
    raw_q_evals = raw.get("question_evaluations", [])

    for idx, entry in enumerate(answers):
        qe = raw_q_evals[idx] if idx < len(raw_q_evals) else {}
        comm_data = qe.get("communication")
        comm = CommunicationAssessment(**comm_data) if comm_data else None

        # Safely parse rating — LLMs sometimes return non-enum values
        try:
            rating = EvalRating(qe.get("rating", "weak"))
        except ValueError:
            rating = _score_to_rating(int(qe.get("score", 0)))

        q_evals.append(
            QuestionEvaluation(
                question_id=entry.question_id,
                question_text=entry.question_text,
                topic=entry.topic,
                answer_transcript=entry.answer_transcript,
                score=int(qe.get("score", 0)),
                rating=rating,
                strengths=qe.get("strengths", []),
                improvements=qe.get("improvements", []),
                feedback=qe.get("feedback", "No feedback available."),
                detailed_feedback=qe.get("detailed_feedback", ""),
                keywords_hit=qe.get("keywords_hit", []),
                communication=comm,
                was_skipped=qe.get("was_skipped", entry.was_skipped),
            )
        )

    overall = int(raw.get("overall_score", 0))

    # Normalize overall_rating
    try:
        overall_rating = EvalRating(raw.get("overall_rating", "weak"))
    except ValueError:
        overall_rating = _score_to_rating(overall)

    return EvaluationReport(
        session_id=session.id,
        candidate_name=session.candidate_name,
        candidate_role=session.candidate_role,
        overall_score=overall,
        overall_rating=overall_rating,
        summary=raw.get("summary", ""),
        executive_summary=raw.get("executive_summary", raw.get("summary", "")),
        question_evaluations=q_evals,
        strengths=raw.get("strengths", []),
        improvements=raw.get("improvements", []),
        recommendation=raw.get("recommendation", _recommendation_from_score(overall)),
        hiring_notes=raw.get("hiring_notes", ""),
        risk_flags=raw.get("risk_flags", []),
    )