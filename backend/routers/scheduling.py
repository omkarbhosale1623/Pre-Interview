"""
routers/scheduling.py — Schedule interviews with link expiry logic.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from config import settings
from models.schemas import (
    ScheduleInterviewRequest, ScheduleInterviewResponse,
    ScheduledInterview, ScheduledStatus, Session, SessionStatus, RecruiterPublic,
)
from routers.auth import get_current_recruiter
from services.email_service import send_invite_email
from services.session_store import store

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/schedule", tags=["Scheduling"])

LINK_BUFFER_MINUTES = 30   # how long after scheduled_at the link stays valid


@router.post("", response_model=ScheduleInterviewResponse)
async def schedule_interview(
    body: ScheduleInterviewRequest,
    recruiter: RecruiterPublic = Depends(get_current_recruiter),
):
    try:
        bank = store.get_bank(body.bank_id)
        if not bank:
            raise HTTPException(status_code=404, detail="Question bank not found.")

        now = datetime.now(timezone.utc)
        scheduled_at = body.scheduled_at
        if not scheduled_at.tzinfo:
            scheduled_at = scheduled_at.replace(tzinfo=timezone.utc)

        # For "Schedule Later": validate future date and set expiry
        link_expires_at = None
        if not body.is_immediate:
            if scheduled_at <= now:
                raise HTTPException(status_code=400, detail="Scheduled time must be in the future.")
            link_expires_at = scheduled_at + timedelta(minutes=LINK_BUFFER_MINUTES)

        scheduled = ScheduledInterview(
            bank_id=body.bank_id,
            candidate_name=body.candidate_name,
            candidate_email=body.candidate_email,
            candidate_role=body.candidate_role,
            scheduled_at=scheduled_at,
            recruiter_email=body.recruiter_email or recruiter.email,
            interviewer_name=body.interviewer_name or recruiter.full_name,
            company_name=body.company_name or recruiter.company_name,
            notes=body.notes,
            is_immediate=body.is_immediate,
            link_expires_at=link_expires_at,
        )
        store.save_scheduled(scheduled)
        logger.info("Scheduled interview created for %s at %s by %s", body.candidate_name, scheduled_at, recruiter.email)

        base_url = settings.app_base_url.rstrip("/")
        interview_link = f"{base_url}/interview/join/{scheduled.token}"
        scheduled_at_str = scheduled_at.strftime("%A, %B %d %Y at %I:%M %p UTC")

        email_sent = False
        try:
            email_sent = send_invite_email(
                to_email=body.candidate_email,
                candidate_name=body.candidate_name,
                candidate_role=body.candidate_role,
                company_name=scheduled.company_name,
                interviewer_name=scheduled.interviewer_name,
                scheduled_at_str=scheduled_at_str,
                interview_link=interview_link,
                bank_name=bank.name,
                question_count=len(bank.questions),
                notes=body.notes,
                is_immediate=body.is_immediate,
                link_expires_at=link_expires_at,
            )
            if email_sent:
                logger.info("Invite email sent to %s", body.candidate_email)
            else:
                logger.warning("SMTP not configured, invite NOT sent to %s", body.candidate_email)
        except Exception as exc:
            logger.error("Failed to send invite email to %s: %s", body.candidate_email, exc, exc_info=True)

        return ScheduleInterviewResponse(
            scheduled_interview=scheduled,
            interview_link=interview_link,
            email_sent=email_sent,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Exception during scheduling for %s: %s", body.candidate_name, exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to schedule interview")


@router.get("/join/{token}", response_model=dict)
async def join_interview(token: str):
    """Candidate joins via unique token. Validates time window."""
    try:
        scheduled = store.get_scheduled_by_token(token)
        if not scheduled:
            logger.warning("Join attempted with invalid token")
            raise HTTPException(status_code=404, detail="Invalid or expired interview link.")

        now = datetime.now(timezone.utc)
        scheduled_at = scheduled.scheduled_at
        if not scheduled_at.tzinfo:
            scheduled_at = scheduled_at.replace(tzinfo=timezone.utc)

        # Time-window validation
        if not scheduled.is_immediate:
            if now < scheduled_at:
                wait_mins = int((scheduled_at - now).total_seconds() / 60)
                logger.info("Candidate %s joined early. Starts in %s mins", scheduled.candidate_name, wait_mins)
                raise HTTPException(
                    status_code=425,
                    detail=f"Your interview hasn't started yet. It is scheduled for {scheduled_at.strftime('%B %d at %I:%M %p UTC')} — {wait_mins} minutes from now.",
                )
            if scheduled.link_expires_at:
                expires = scheduled.link_expires_at
                if not expires.tzinfo:
                    expires = expires.replace(tzinfo=timezone.utc)
                if now > expires:
                    scheduled.status = ScheduledStatus.EXPIRED
                    store.save_scheduled(scheduled)
                    logger.warning("Join attempted for expired link (candidate=%s)", scheduled.candidate_name)
                    raise HTTPException(
                        status_code=410,
                        detail="This interview link has expired. The 30-minute window has passed. Please contact your recruiter.",
                    )

        if scheduled.status == ScheduledStatus.COMPLETED:
            raise HTTPException(status_code=410, detail="This interview has already been completed.")
        if scheduled.status == ScheduledStatus.EXPIRED:
            raise HTTPException(status_code=410, detail="This interview link has expired.")

        bank = store.get_bank(scheduled.bank_id)
        if not bank:
            logger.error("Question bank %s not found for scheduled %s", scheduled.bank_id, scheduled.id)
            raise HTTPException(status_code=500, detail="Question bank no longer available.")

        # Idempotent — return existing active session
        if scheduled.session_id:
            session = store.get_session(scheduled.session_id)
            if session and session.status in (SessionStatus.ACTIVE, SessionStatus.WAITING):
                logger.info("Candidate %s rejoined existing session %s", scheduled.candidate_name, session.id)
                return {"session": session.model_dump(mode="json"), "bank": bank.model_dump(mode="json"), "scheduled": scheduled.model_dump(mode="json")}

        # Create and start new session
        session = Session(
            bank_id=scheduled.bank_id,
            candidate_name=scheduled.candidate_name,
            candidate_role=scheduled.candidate_role,
            candidate_email=scheduled.candidate_email,
            recruiter_email=scheduled.recruiter_email,
            status=SessionStatus.ACTIVE,
            started_at=now,
        )
        store.save_session(session)
        scheduled.session_id = session.id
        scheduled.status = ScheduledStatus.IN_PROGRESS
        store.save_scheduled(scheduled)

        logger.info("Candidate %s joined successfully. Session %s created", scheduled.candidate_name, session.id)
        return {"session": session.model_dump(mode="json"), "bank": bank.model_dump(mode="json"), "scheduled": scheduled.model_dump(mode="json")}

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Exception in join logic for token %s: %s", token, exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to load interview")


@router.get("/list", response_model=list[ScheduledInterview])
async def list_scheduled(recruiter: RecruiterPublic = Depends(get_current_recruiter)):
    try:
        return store.list_scheduled()
    except Exception as exc:
        logger.error("Failed to list scheduled interviews: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch scheduled interviews")


@router.get("/{scheduled_id}", response_model=ScheduledInterview)
async def get_scheduled(scheduled_id: str, recruiter: RecruiterPublic = Depends(get_current_recruiter)):
    try:
        s = store.get_scheduled(scheduled_id)
        if not s:
            raise HTTPException(status_code=404, detail="Scheduled interview not found.")
        return s
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to fetch scheduled interview %s: %s", scheduled_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch scheduled interview")
