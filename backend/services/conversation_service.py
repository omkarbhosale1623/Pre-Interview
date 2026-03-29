"""
services/conversation_service.py — Interview conversation orchestration.

LATENCY FIX (key change):
  The LLM acknowledgement call was in the critical path:
    answer recorded → LLM ack (2-5s) → TTS synthesis (1-2s) → return
  Total silence between questions: 4-8 seconds.

  Fix: LLM removed from the real-time path. Bot text is generated instantly
  (<5ms) using simple connector phrases + the next question text.
  Per-question delay is now just TTS synthesis time (~1s).

Other fixes:
  * Per-session asyncio.Lock prevents double-call race (React StrictMode)
  * Initialization state derived from session.answers (survives restarts)
"""
from __future__ import annotations

import asyncio
import random
from datetime import datetime
from typing import TypedDict, Optional
import logging

from langgraph.graph import StateGraph

from models.schemas import AnswerEntry, Session, SessionStatus
from services.session_store import store

logger = logging.getLogger(__name__)

# ── Per-session locks ────────────────────────────────────────────────────────
_session_locks: dict[str, asyncio.Lock] = {}


def _get_session_lock(session_id: str) -> asyncio.Lock:
    if session_id not in _session_locks:
        _session_locks[session_id] = asyncio.Lock()
    return _session_locks[session_id]


# ── Natural connector phrases (no LLM needed) ────────────────────────────────
_CONNECTORS = [
    "Got it. ",
    "Thank you. ",
    "Understood. ",
    "Noted. ",
    "Good. ",
    "All right. ",
    "",  # silence connector — also natural
]


def _next_q_text(q_num: int, total: int, question: str, skipped: bool = False) -> str:
    connector = random.choice(_CONNECTORS)
    if skipped:
        connector = "Let's move on. "
    return f"{connector}Question {q_num} of {total}: {question}"


# ── Conversation state ───────────────────────────────────────────────────────

class ConvState(TypedDict, total=False):
    session: Session
    last_transcript: Optional[str]
    bot_text: Optional[str]
    done: bool


def _make_graph():
    graph = StateGraph(state_schema=ConvState)

    async def start_node(state: ConvState) -> ConvState:
        """Greeting + first question. Skipped on reconnect."""
        session = state["session"]
        if session.current_question_index > 0 or session.answers:
            return state  # reconnect — skip greeting

        bank = store.get_bank(session.bank_id)
        role = f" for the {session.candidate_role} role" if session.candidate_role else ""

        if bank and bank.questions:
            total = len(bank.questions)
            first_q = bank.questions[0].text
            greeting = (
                f"Hello {session.candidate_name}, welcome to your AI interview{role}. "
                f"I'll ask you {total} question{'s' if total != 1 else ''}. "
                f"Please answer each one clearly. "
                f"Here's your first question: {first_q}"
            )
        else:
            greeting = f"Hello {session.candidate_name}, welcome. Let's begin."

        state["bot_text"] = greeting
        logger.info("Greeting generated for session %s", session.id)
        return state

    async def handle_node(state: ConvState) -> ConvState:
        """Record answer → advance index → return next question text instantly."""
        session = state["session"]
        last = state.get("last_transcript")
        bank = store.get_bank(session.bank_id)

        if not bank or not bank.questions:
            state["bot_text"] = "Sorry, the question bank is unavailable."
            state["done"] = True
            return state

        skipped_answer = False

        # Record answer (only when transcript was provided)
        if last is not None:
            skipped_answer = last.strip() in [
                "", "(skipped — no response)", "(No answer provided)",
            ]
            if session.current_question_index < len(bank.questions):
                q = bank.questions[session.current_question_index]
                entry = AnswerEntry(
                    question_id=q.id,
                    question_text=q.text,
                    topic=q.topic,
                    answer_transcript=last if not skipped_answer else "(skipped — no response)",
                    answer_duration_s=None,
                    was_skipped=skipped_answer,
                )
                session.answers.append(entry)
                session.current_question_index += 1
                store.save_session(session)
                logger.info(
                    "Answer recorded for session %s, q_index=%d",
                    session.id, session.current_question_index - 1,
                )

        # Check completion
        if session.current_question_index >= len(bank.questions):
            total = len(bank.questions)
            state["bot_text"] = (
                f"That's all {total} questions. "
                "Thank you so much for your time. "
                "Your responses have been submitted and the team will be in touch. "
                "Best of luck!"
            )
            state["done"] = True
            if session.status != SessionStatus.COMPLETED:
                session.status = SessionStatus.COMPLETED
                session.completed_at = datetime.utcnow()
                store.save_session(session)
                logger.info(
                    "Session %s completed with %d answers",
                    session.id, len(session.answers),
                )
            return state

        # Reconnect mid-session — re-ask current question
        if last is None and session.current_question_index > 0:
            next_q = bank.questions[session.current_question_index].text
            q_num = session.current_question_index + 1
            total = len(bank.questions)
            state["bot_text"] = f"We're on question {q_num} of {total}: {next_q}"
            return state

        # Normal flow — instant next question, NO LLM call
        if last is not None:
            next_q = bank.questions[session.current_question_index].text
            q_num = session.current_question_index + 1
            total = len(bank.questions)
            state["bot_text"] = _next_q_text(q_num, total, next_q, skipped=skipped_answer)

        return state

    graph.add_node("start", start_node)
    graph.add_node("handle", handle_node)
    graph.set_entry_point("start")
    graph.add_edge("start", "handle")
    graph.set_finish_point("handle")
    return graph.compile()


_conversation_graph = _make_graph()


async def advance_conversation(
    session: Session, transcript: Optional[str] = None
) -> tuple[str | None, bool]:
    """
    Advance the interview. Per-session lock prevents concurrent execution.
    Returns (bot_text, done) — typically in <50ms since no LLM is called.
    """
    lock = _get_session_lock(session.id)
    async with lock:
        state: ConvState = {
            "session": session,
            "last_transcript": transcript,
            "bot_text": None,
            "done": False,
        }
        new_state = await _conversation_graph.ainvoke(state)
        return new_state.get("bot_text"), bool(new_state.get("done", False))
