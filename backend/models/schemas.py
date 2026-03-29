from __future__ import annotations
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime
import uuid


# ── Enums ────────────────────────────────────────────────────────────────────

class SessionStatus(str, Enum):
    WAITING   = "waiting"
    ACTIVE    = "active"
    COMPLETED = "completed"
    EVALUATED = "evaluated"


class EvalRating(str, Enum):
    STRONG   = "strong"
    GOOD     = "good"
    AVERAGE  = "average"
    WEAK     = "weak"


class ScheduledStatus(str, Enum):
    SCHEDULED   = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED   = "completed"
    EXPIRED     = "expired"


# ── Recruiter Auth ────────────────────────────────────────────────────────────

class Recruiter(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: str
    password_hash: str
    full_name: str
    company_name: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RecruiterPublic(BaseModel):
    """Safe to send to frontend — no password_hash."""
    id: str
    email: str
    full_name: str
    company_name: Optional[str] = None


class RecruiterSignupRequest(BaseModel):
    email: str
    password: str
    full_name: str
    company_name: Optional[str] = None


class RecruiterSigninRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    token: str
    recruiter: RecruiterPublic


# ── Question Bank ─────────────────────────────────────────────────────────────

class Question(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    text: str
    topic: Optional[str] = None
    difficulty: Optional[str] = None
    expected_keywords: list[str] = []


class QuestionBank(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    role: Optional[str] = None
    questions: list[Question]
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def count(self) -> int:
        return len(self.questions)


# ── Session ───────────────────────────────────────────────────────────────────

class AnswerEntry(BaseModel):
    question_id: str
    question_text: str
    topic: Optional[str] = None
    answer_transcript: str
    answer_duration_s: Optional[float] = None
    was_skipped: bool = False          # True if no response after 2 repeats
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class Session(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    bank_id: str
    candidate_name: str
    candidate_role: Optional[str] = None
    candidate_email: Optional[str] = None     # for sending thank-you
    recruiter_email: Optional[str] = None     # for sending report
    status: SessionStatus = SessionStatus.WAITING
    current_question_index: int = 0
    answers: list[AnswerEntry] = []
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


# ── Scheduled Interview ───────────────────────────────────────────────────────

class ScheduleInterviewRequest(BaseModel):
    bank_id: str
    candidate_name: str
    candidate_email: str
    candidate_role: Optional[str] = None
    scheduled_at: datetime
    recruiter_email: str                      # who gets the report
    interviewer_name: Optional[str] = None
    company_name: Optional[str] = None
    notes: Optional[str] = None
    is_immediate: bool = False                # True = "Schedule Now" (no time restriction)


class ScheduledInterview(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    token: str = Field(default_factory=lambda: str(uuid.uuid4()))
    bank_id: str
    candidate_name: str
    candidate_email: str
    candidate_role: Optional[str] = None
    scheduled_at: datetime
    recruiter_email: str
    interviewer_name: Optional[str] = None
    company_name: Optional[str] = None
    notes: Optional[str] = None
    is_immediate: bool = False
    link_expires_at: Optional[datetime] = None    # None = never expires (immediate)
    status: ScheduledStatus = ScheduledStatus.SCHEDULED
    session_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ScheduleInterviewResponse(BaseModel):
    scheduled_interview: ScheduledInterview
    interview_link: str
    email_sent: bool


# ── Request / Response ────────────────────────────────────────────────────────

class ConversationRequest(BaseModel):
    transcript: Optional[str] = None

class ConversationResponse(BaseModel):
    bot_text: Optional[str] = None
    audio: Optional[str] = None
    done: bool
    # current question index after processing (0‑based). this lets the
    # frontend keep its header in sync with the server.
    question_index: Optional[int] = None
    total_questions: Optional[int] = None



class CreateSessionRequest(BaseModel):
    bank_id: str
    candidate_name: str
    candidate_role: Optional[str] = None
    candidate_email: Optional[str] = None
    recruiter_email: Optional[str] = None


class SubmitAnswerRequest(BaseModel):
    session_id: str
    question_id: str
    answer_transcript: str
    answer_duration_s: Optional[float] = None
    was_skipped: bool = False


class NextQuestionResponse(BaseModel):
    session_id: str
    question: Optional[Question] = None
    question_index: int
    total_questions: int
    is_complete: bool


# ── Evaluation ────────────────────────────────────────────────────────────────

class CommunicationAssessment(BaseModel):
    clarity: int = Field(ge=0, le=10)
    confidence: int = Field(ge=0, le=10)
    depth: int = Field(ge=0, le=10)
    relevance: int = Field(ge=0, le=10)


class QuestionEvaluation(BaseModel):
    question_id: str
    question_text: str
    topic: Optional[str] = None
    answer_transcript: str
    score: int = Field(ge=0, le=100)
    rating: EvalRating
    strengths: list[str]
    improvements: list[str]
    feedback: str
    detailed_feedback: str                         # 2-3 paragraph in-depth analysis
    keywords_hit: list[str] = []
    communication: Optional[CommunicationAssessment] = None
    was_skipped: bool = False


class EvaluationReport(BaseModel):
    session_id: str
    candidate_name: str
    candidate_role: Optional[str]
    overall_score: int = Field(ge=0, le=100)
    overall_rating: EvalRating
    summary: str
    executive_summary: str                         # longer paragraph for recruiter
    question_evaluations: list[QuestionEvaluation]
    strengths: list[str]
    improvements: list[str]
    recommendation: str
    hiring_notes: str                              # private notes for recruiter
    risk_flags: list[str] = []                    # red flags if any
    generated_at: datetime = Field(default_factory=datetime.utcnow)
