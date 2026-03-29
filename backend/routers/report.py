"""
routers/report.py — Generate a plain-text interview report.

Endpoints:
  GET /report/{session_id}        — JSON report (same as evaluation)
  GET /report/{session_id}/text   — human-readable .txt report
"""
import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse

from models.schemas import EvaluationReport
from services.session_store import store

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/report", tags=["Report"])


# ── JSON report (re-expose evaluation) ───────────────────────────────────────

@router.get("/{session_id}", response_model=EvaluationReport)
async def get_report_json(session_id: str):
    """Return full evaluation report as JSON."""
    try:
        report = store.get_report(session_id)
        if not report:
            raise HTTPException(status_code=404, detail="Report not found. Run evaluation first.")
        return report
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to fetch JSON report for %s: %s", session_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve report.")


# ── Text report ───────────────────────────────────────────────────────────────

@router.get("/{session_id}/text", response_class=PlainTextResponse)
async def get_report_text(session_id: str):
    """Generate a human-readable plain-text report for download or email."""
    try:
        report = store.get_report(session_id)
        if not report:
            raise HTTPException(status_code=404, detail="Report not found. Run evaluation first.")
        return _render_text_report(report)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to generate text report for %s: %s", session_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate text report.")


# ── Renderer ──────────────────────────────────────────────────────────────────

def _render_text_report(r: EvaluationReport) -> str:
    sep = "=" * 70
    thin = "-" * 70

    rating_emoji = {
        "strong": "⭐⭐⭐⭐⭐",
        "good": "⭐⭐⭐⭐",
        "average": "⭐⭐⭐",
        "weak": "⭐⭐",
    }

    lines = [
        sep,
        "INTERVIEW EVALUATION REPORT",
        sep,
        f"Candidate   : {r.candidate_name}",
        f"Role        : {r.candidate_role or 'Not specified'}",
        f"Generated   : {r.generated_at.strftime('%Y-%m-%d %H:%M UTC')}",
        f"Session ID  : {r.session_id}",
        "",
        thin,
        "OVERALL RESULT",
        thin,
        f"Score          : {r.overall_score} / 100",
        f"Rating         : {r.overall_rating.upper()} {rating_emoji.get(r.overall_rating, '')}",
        f"Recommendation : {r.recommendation}",
        "",
        "Summary:",
        _wrap(r.summary),
        "",
        thin,
        "TOP STRENGTHS",
        thin,
    ]
    for s in r.strengths:
        lines.append(f"  ✓ {s}")

    lines += ["", thin, "AREAS FOR IMPROVEMENT", thin]
    for i in r.improvements:
        lines.append(f"  ✗ {i}")

    lines += ["", sep, "QUESTION-BY-QUESTION BREAKDOWN", sep]
    for idx, qe in enumerate(r.question_evaluations, 1):
        lines += [
            "",
            f"Q{idx}: {qe.question_text}",
            thin,
            f"  Score    : {qe.score}/100  ({qe.rating.upper()})",
            f"  Feedback : {qe.feedback}",
        ]
        if qe.strengths:
            lines.append(f"  Strengths: {', '.join(qe.strengths)}")
        if qe.improvements:
            lines.append(f"  Improve  : {', '.join(qe.improvements)}")
        if qe.keywords_hit:
            lines.append(f"  Keywords : {', '.join(qe.keywords_hit)}")
        lines.append("")
        lines.append(f"  Answer:\n    {_wrap(qe.answer_transcript, indent=4)}")

    lines += ["", sep, "END OF REPORT", sep]
    return "\n".join(lines)


def _wrap(text: str, width: int = 70, indent: int = 0) -> str:
    """Simple word-wrap for text."""
    words = text.split()
    lines, current = [], []
    for word in words:
        if sum(len(w) + 1 for w in current) + len(word) > width:
            lines.append(" " * indent + " ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(" " * indent + " ".join(current))
    return "\n".join(lines)
