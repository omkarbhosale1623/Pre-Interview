"""
routers/evaluation.py — Evaluate completed interviews via LLM.

Fixes applied:
  * Per-session asyncio.Lock prevents double-evaluation when two requests
    arrive simultaneously (idempotency check had a race condition).
  * A DB-level guard (re-check status inside the lock) provides a second
    safety net after the lock is acquired.
  * Recommendation field is normalized to standard values before emailing.

Endpoints:
  POST /evaluation/{session_id}  — run evaluation + email
  GET  /evaluation/{session_id}  — get evaluation (JSON)
"""
import asyncio
import logging
from fastapi import APIRouter, HTTPException

from models.schemas import EvaluationReport, SessionStatus
from services.ai_evaluator import evaluate_session
from services.email_service import send_report_to_recruiter, send_thankyou_to_candidate
from services.session_store import store

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/evaluation", tags=["Evaluation"])

# Per-session evaluation locks — prevents the double-call that was sending two
# emails with different scores when the frontend fired two POST requests.
_eval_locks: dict[str, asyncio.Lock] = {}


def _get_eval_lock(session_id: str) -> asyncio.Lock:
    if session_id not in _eval_locks:
        _eval_locks[session_id] = asyncio.Lock()
    return _eval_locks[session_id]


def _normalize_recommendation(rec: str) -> str:
    """
    Normalize LLM-generated recommendation strings to standard values.
    LLMs sometimes return full sentences like 'The candidate should be hired'.
    """
    if not rec:
        return "Consider"
    r = rec.lower()
    if "strong hire" in r or "strongly hire" in r or "strongly recommend" in r:
        return "Strong Hire"
    if "no hire" in r or "not hire" in r or "do not hire" in r or "not recommend" in r:
        return "No Hire"
    if "hire" in r and "no" not in r:
        return "Hire"
    if "consider" in r or "maybe" in r or "potential" in r:
        return "Consider"
    # Clamp to 50 chars for email subject safety
    return rec[:50] if len(rec) > 50 else rec


@router.post("/{session_id}", response_model=EvaluationReport)
async def run_evaluation(session_id: str):
    """Run an AI evaluation on a completed session and dispatch emails."""

    # Validate before acquiring lock
    session = store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status not in (SessionStatus.COMPLETED, SessionStatus.EVALUATED):
        raise HTTPException(
            status_code=400,
            detail=f"Session must be completed first. Current status: {session.status}",
        )
    if not session.answers:
        raise HTTPException(status_code=400, detail="No answers to evaluate")

    lock = _get_eval_lock(session_id)

    async with lock:
        # Re-fetch inside lock — the first request may have already evaluated
        session = store.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        # Idempotency: already evaluated → return existing report
        if session.status == SessionStatus.EVALUATED:
            existing_report = store.get_report(session_id)
            if existing_report:
                logger.info("Evaluation already completed for %s. Returning existing.", session_id)
                return existing_report

        # ── Run AI evaluation ─────────────────────────────────────────────
        try:
            logger.info(
                "Starting AI evaluation for session %s (candidate: %s)",
                session_id, session.candidate_name
            )
            report = await evaluate_session(session)

            # Normalize recommendation to standard enum values
            report.recommendation = _normalize_recommendation(report.recommendation)

            store.save_report(report)
            session.status = SessionStatus.EVALUATED
            store.save_session(session)
            logger.info("Evaluation completed successfully for %s", session_id)

        except Exception as eval_exc:
            logger.error("AI Evaluation failed for %s: %s", session_id, eval_exc, exc_info=True)
            raise HTTPException(status_code=500, detail="LLM evaluation failed. See server logs.")

        # ── Resolve recruiter email ───────────────────────────────────────
        recruiter_email = session.recruiter_email
        if not recruiter_email:
            try:
                scheduled = store.get_scheduled_by_session(session_id)
                if scheduled and scheduled.recruiter_email:
                    recruiter_email = scheduled.recruiter_email
            except Exception as store_exc:
                logger.warning("Failed to lookup scheduled interview for email: %s", store_exc)

        # ── Send report to recruiter ──────────────────────────────────────
        if recruiter_email:
            try:
                sent = send_report_to_recruiter(report, recruiter_email, session.candidate_email)
                if sent:
                    logger.info("Report emailed to recruiter: %s", recruiter_email)
                else:
                    logger.warning("Report NOT sent — SMTP not configured.")
            except Exception as exc:
                logger.error("Email to recruiter failed: %s", exc)
        else:
            logger.warning(
                "No recruiter_email on session %s — report saved but not emailed.", session_id
            )

        # ── Send thank-you to candidate (once, inside the lock) ───────────
        if session.candidate_email:
            try:
                scheduled = store.get_scheduled_by_session(session_id)
                company = scheduled.company_name if scheduled else None
                sent = send_thankyou_to_candidate(
                    session.candidate_email, session.candidate_name, company
                )
                if sent:
                    logger.info("Thank-you email sent to candidate: %s", session.candidate_email)
            except Exception as exc:
                logger.warning("Failed to send thank-you to candidate: %s", exc)

        return report


@router.get("/{session_id}", response_model=EvaluationReport)
async def get_evaluation(session_id: str):
    """Fetch an existing JSON evaluation report."""
    try:
        report = store.get_report(session_id)
        if not report:
            raise HTTPException(
                status_code=404,
                detail="No evaluation found. Run POST /evaluation/{session_id} first.",
            )
        return report
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to fetch evaluation %s: %s", session_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve evaluation.")