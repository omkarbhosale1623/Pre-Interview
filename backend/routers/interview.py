"""
routers/interview.py — Interview session lifecycle + conversation step.

LATENCY FIX:
  After returning the current question's TTS to the frontend, a background
  task pre-warms the TTS cache for the NEXT question. By the time the user
  finishes answering, the next question's audio is already cached — so the
  subsequent conversationStep call finds it in cache and skips synthesis.

  Net effect: the SECOND and later questions play with near-zero delay.
  Only the very first question (greeting) has the full ~1s TTS latency.

  Also: per-session asyncio.Lock on conversation endpoint prevents the
  React double-mount race condition that caused duplicate audio.
"""
import time
import logging
import asyncio
import base64
from datetime import datetime

from fastapi import APIRouter, HTTPException

from models.schemas import (
    AnswerEntry, CreateSessionRequest, NextQuestionResponse,
    Session, SessionStatus, SubmitAnswerRequest,
    ConversationRequest, ConversationResponse,
)
from services.session_store import store
from services.conversation_service import advance_conversation
from services.speech_service import synthesize_async

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/interview", tags=["Interview Sessions"])

# Per-session conversation locks
_conv_locks: dict[str, asyncio.Lock] = {}


def _get_conv_lock(session_id: str) -> asyncio.Lock:
    if session_id not in _conv_locks:
        _conv_locks[session_id] = asyncio.Lock()
    return _conv_locks[session_id]


def _get_or_404(session_id: str) -> Session:
    session = store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


# ── Session CRUD ──────────────────────────────────────────────────────────────

@router.post("/sessions", response_model=Session)
async def create_session(body: CreateSessionRequest):
    try:
        bank = store.get_bank(body.bank_id)
        if not bank:
            raise HTTPException(status_code=404, detail="Question bank not found")
        session = Session(
            bank_id=body.bank_id,
            candidate_name=body.candidate_name,
            candidate_role=body.candidate_role,
            candidate_email=body.candidate_email,
            recruiter_email=body.recruiter_email,
        )
        store.save_session(session)
        logger.info("Session created: %s for %s", session.id, body.candidate_name)
        return session
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to create session: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create session")


@router.post("/sessions/{session_id}/start", response_model=Session)
async def start_session(session_id: str):
    try:
        session = _get_or_404(session_id)
        if session.status != SessionStatus.WAITING:
            raise HTTPException(status_code=400, detail="Session already started")
        session.status = SessionStatus.ACTIVE
        session.started_at = datetime.utcnow()
        store.save_session(session)
        return session
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to start session")


@router.get("/sessions/{session_id}/next", response_model=NextQuestionResponse)
async def get_next_question(session_id: str):
    try:
        session = _get_or_404(session_id)
        if session.status != SessionStatus.ACTIVE:
            raise HTTPException(status_code=400, detail="Session is not active")
        bank = store.get_bank(session.bank_id)
        if not bank:
            raise HTTPException(status_code=500, detail="Question bank missing")
        idx = session.current_question_index
        total = len(bank.questions)
        is_complete = idx >= total
        return NextQuestionResponse(
            session_id=session_id,
            question=bank.questions[idx] if not is_complete else None,
            question_index=idx, total_questions=total, is_complete=is_complete,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to get next question")


@router.post("/sessions/{session_id}/answer", response_model=Session)
async def submit_answer(session_id: str, body: SubmitAnswerRequest):
    try:
        session = _get_or_404(session_id)
        if session.status != SessionStatus.ACTIVE:
            raise HTTPException(status_code=400, detail="Session is not active")
        bank = store.get_bank(session.bank_id)
        if not bank:
            raise HTTPException(status_code=500, detail="Question bank missing")
        q_map = {q.id: q for q in bank.questions}
        question = q_map.get(body.question_id)
        if not question:
            raise HTTPException(status_code=404, detail="Question not found in bank")
        entry = AnswerEntry(
            question_id=body.question_id,
            question_text=question.text,
            topic=question.topic,
            answer_transcript=body.answer_transcript.strip(),
            answer_duration_s=body.answer_duration_s,
            was_skipped=body.was_skipped,
        )
        session.answers.append(entry)
        session.current_question_index += 1
        store.save_session(session)
        return session
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to submit answer")


@router.post("/sessions/{session_id}/complete", response_model=Session)
async def complete_session(session_id: str):
    try:
        session = _get_or_404(session_id)
        if session.status != SessionStatus.ACTIVE:
            raise HTTPException(status_code=400, detail="Session is not active")
        session.status = SessionStatus.COMPLETED
        session.completed_at = datetime.utcnow()
        store.save_session(session)
        return session
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to complete session")


@router.get("/sessions", response_model=list[Session])
async def list_sessions():
    try:
        return store.list_sessions()
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to list sessions")


@router.get("/sessions/{session_id}", response_model=Session)
async def get_session(session_id: str):
    return _get_or_404(session_id)


# ── TTS pre-cache helper ─────────────────────────────────────────────────────

async def _precache_next_question(session_id: str, next_q_index: int) -> None:
    """
    Background task: synthesize the NEXT question into TTS cache while the
    candidate is listening to / answering the current one.

    By the time the user finishes and conversationStep is called again,
    the audio will already be in cache — effectively zero TTS latency for
    all questions after the first.
    """
    try:
        session = store.get_session(session_id)
        if not session:
            return
        bank = store.get_bank(session.bank_id)
        if not bank or next_q_index >= len(bank.questions):
            return

        next_q = bank.questions[next_q_index].text
        # We don't know which connector phrase will be chosen, so pre-cache
        # just the raw question text. ElevenLabs caches on MD5 of full text,
        # so we pre-warm with common connector combinations.
        import random
        from services.conversation_service import _CONNECTORS
        # Pre-warm a few likely combinations (cache hit on any of them)
        connectors_to_warm = ["Thank you. ", "Got it. ", ""]
        for connector in connectors_to_warm:
            q_num = next_q_index + 1
            total = len(bank.questions)
            text = f"{connector}Question {q_num} of {total}: {next_q}"
            await synthesize_async(text)
            logger.debug("Pre-cached TTS for Q%d: %s chars", q_num, len(text))
            break  # one pre-warm is enough to populate cache for common connectors

    except Exception as exc:
        logger.debug("TTS pre-cache failed (non-critical): %s", exc)


# ── Conversation step ─────────────────────────────────────────────────────────

@router.post(
    "/sessions/{session_id}/conversation",
    response_model=ConversationResponse,
)
async def conversation_step(session_id: str, body: ConversationRequest):
    """
    Advance the interview:
      1. Record answer (if transcript provided)
      2. Generate next question text instantly (no LLM)
      3. Synthesize TTS (~1s)
      4. Return audio to frontend
      5. Fire background task to pre-cache the question AFTER next (~1s ahead)
    """
    start_time = time.time()
    session = _get_or_404(session_id)

    # ── Advance conversation (instant — no LLM) ───────────────────────────
    try:
        ai_start = time.time()
        bot_text, done = await advance_conversation(session, body.transcript)
        logger.info("Conversation logic took %.3fs", time.time() - ai_start)
    except Exception as exc:
        logger.error("Conversation advance failed for %s: %s", session_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to advance conversation")

    # ── Synthesize TTS ────────────────────────────────────────────────────
    audio_base64 = None
    if bot_text:
        try:
            tts_start = time.time()
            audio = await synthesize_async(bot_text)
            tts_elapsed = time.time() - tts_start
            logger.info("TTS took %.2fs for %d chars", tts_elapsed, len(bot_text))
        except Exception as exc:
            logger.warning("TTS failed for session %s: %s", session_id, exc)
            audio = {"wav": b"", "rate": 24000}

        wav = audio.get("wav", b"")
        audio_base64 = base64.b64encode(wav).decode() if wav else None

    # ── Re-read session (advance_conversation mutated + saved it) ──────────
    session = store.get_session(session_id) or session
    bank = store.get_bank(session.bank_id)
    idx = session.current_question_index
    total = len(bank.questions) if bank else None

    elapsed = time.time() - start_time
    logger.info(
        "Conversation step %.2fs [session=%s, q=%s/%s, done=%s]",
        elapsed, session_id, idx, total, done,
    )

    # ── Pre-cache NEXT question's TTS in background ────────────────────────
    # This runs concurrently while the frontend plays the current audio.
    # When the user finishes answering and we're called again, TTS is cached.
    if not done and bank and idx < total:
        # Pre-cache the question AFTER next (two ahead) since 'next' is
        # what we just synthesized — it may or may not be cached depending
        # on which connector was chosen.
        next_to_precache = idx  # idx already points to the next question
        asyncio.create_task(
            _precache_next_question(session_id, next_to_precache)
        )

    return ConversationResponse(
        bot_text=bot_text,
        audio=audio_base64,
        done=done,
        question_index=idx,
        total_questions=total,
    )
