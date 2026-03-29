"""
services/postgres_store.py — PostgreSQL persistence using psycopg2.
"""
from __future__ import annotations
import hashlib
import json
import uuid
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any

import psycopg2
from psycopg2.extras import RealDictCursor

from config import settings
from models.schemas import (
    AnswerEntry, EvaluationReport, Question, QuestionBank,
    Recruiter, RecruiterPublic, ScheduledInterview, ScheduledStatus,
    Session, SessionStatus,
)

logger = logging.getLogger(__name__)

def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

class PostgresStore:
    def __init__(self):
        self._url = settings.database_url
        self._init_db()

    def _conn(self):
        # Neon (and many Postgres hosts) require SSL. The connection string should have sslmode=require.
        conn = psycopg2.connect(self._url)
        return conn

    def _init_db(self) -> None:
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS recruiters (
                        id TEXT PRIMARY KEY,
                        email TEXT UNIQUE NOT NULL,
                        password_hash TEXT NOT NULL,
                        full_name TEXT NOT NULL,
                        company_name TEXT,
                        created_at TIMESTAMP WITH TIME ZONE NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS recruiter_sessions (
                        token TEXT PRIMARY KEY,
                        recruiter_id TEXT NOT NULL REFERENCES recruiters(id),
                        expires_at TIMESTAMP WITH TIME ZONE NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS question_banks (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        role TEXT,
                        questions_json TEXT NOT NULL,
                        created_at TIMESTAMP WITH TIME ZONE NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS sessions (
                        id TEXT PRIMARY KEY,
                        bank_id TEXT NOT NULL,
                        candidate_name TEXT NOT NULL,
                        candidate_role TEXT,
                        candidate_email TEXT,
                        recruiter_email TEXT,
                        status TEXT NOT NULL,
                        current_question_index INTEGER NOT NULL DEFAULT 0,
                        answers_json TEXT NOT NULL DEFAULT '[]',
                        started_at TIMESTAMP WITH TIME ZONE,
                        completed_at TIMESTAMP WITH TIME ZONE
                    );
                    CREATE TABLE IF NOT EXISTS evaluation_reports (
                        session_id TEXT PRIMARY KEY,
                        report_json TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS scheduled_interviews (
                        id TEXT PRIMARY KEY,
                        token TEXT UNIQUE NOT NULL,
                        bank_id TEXT NOT NULL,
                        candidate_name TEXT NOT NULL,
                        candidate_email TEXT NOT NULL,
                        candidate_role TEXT,
                        scheduled_at TIMESTAMP WITH TIME ZONE NOT NULL,
                        recruiter_email TEXT NOT NULL,
                        interviewer_name TEXT,
                        company_name TEXT,
                        notes TEXT,
                        is_immediate BOOLEAN NOT NULL DEFAULT FALSE,
                        link_expires_at TIMESTAMP WITH TIME ZONE,
                        status TEXT NOT NULL,
                        session_id TEXT,
                        created_at TIMESTAMP WITH TIME ZONE NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_scheduled_token ON scheduled_interviews(token);
                    CREATE INDEX IF NOT EXISTS idx_recruiter_email ON recruiters(email);
                """)
                conn.commit()
        except Exception as exc:
            logger.error("Failed to initialize PostgreSQL DB: %s", exc, exc_info=True)
            # Don't raise here to allow app startup even if DB is momentarily unreachable
        finally:
            conn.close()

    def _run(self, fn, commit=False):
        conn = self._conn()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                result = fn(cur)
                if commit:
                    conn.commit()
                return result
        except Exception as exc:
            logger.error("DB Error: %s", exc, exc_info=True)
            if commit:
                conn.rollback()
            raise
        finally:
            conn.close()

    # ── Recruiter Auth ────────────────────────────────────────────────────────

    def create_recruiter(self, email: str, password: str, full_name: str, company_name: Optional[str]) -> Optional[Recruiter]:
        def _do(cur):
            cur.execute("SELECT id FROM recruiters WHERE email = LOWER(%s)", (email,))
            if cur.fetchone():
                return None
            rec = Recruiter(
                email=email.lower(), password_hash=_hash_password(password),
                full_name=full_name, company_name=company_name,
            )
            cur.execute(
                "INSERT INTO recruiters (id, email, password_hash, full_name, company_name, created_at) VALUES (%s,%s,%s,%s,%s,%s)",
                (rec.id, rec.email, rec.password_hash, rec.full_name, rec.company_name, rec.created_at),
            )
            return rec
        return self._run(_do, commit=True)

    def authenticate_recruiter(self, email: str, password: str) -> Optional[RecruiterPublic]:
        def _do(cur):
            cur.execute("SELECT * FROM recruiters WHERE email = LOWER(%s)", (email,))
            row = cur.fetchone()
            if not row:
                return None
            if row["password_hash"] != _hash_password(password):
                return None
            return RecruiterPublic(
                id=row["id"], email=row["email"],
                full_name=row["full_name"], company_name=row["company_name"],
            )
        return self._run(_do)

    def create_recruiter_session(self, recruiter_id: str, expire_hours: int = 72) -> str:
        token = str(uuid.uuid4())
        expires = datetime.now(timezone.utc) + timedelta(hours=expire_hours)
        def _do(cur):
            cur.execute(
                "INSERT INTO recruiter_sessions (token, recruiter_id, expires_at) VALUES (%s,%s,%s)",
                (token, recruiter_id, expires),
            )
        self._run(_do, commit=True)
        return token

    def get_recruiter_by_token(self, token: str) -> Optional[RecruiterPublic]:
        def _do(cur):
            cur.execute("""
                SELECT r.id, r.email, r.full_name, r.company_name, rs.expires_at
                FROM recruiter_sessions rs
                JOIN recruiters r ON r.id = rs.recruiter_id
                WHERE rs.token = %s
            """, (token,))
            row = cur.fetchone()
            if not row:
                return None
            expires = row["expires_at"]
            if expires and expires < datetime.now(timezone.utc):
                return None
            return RecruiterPublic(
                id=row["id"], email=row["email"],
                full_name=row["full_name"], company_name=row["company_name"],
            )
        return self._run(_do)

    def delete_recruiter_session(self, token: str) -> None:
        def _do(cur):
            cur.execute("DELETE FROM recruiter_sessions WHERE token = %s", (token,))
        self._run(_do, commit=True)

    # ── Question Banks ────────────────────────────────────────────────────────

    def save_bank(self, bank: QuestionBank) -> QuestionBank:
        def _do(cur):
            cur.execute("""
                INSERT INTO question_banks (id, name, role, questions_json, created_at)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    role = EXCLUDED.role,
                    questions_json = EXCLUDED.questions_json,
                    created_at = EXCLUDED.created_at
            """, (bank.id, bank.name, bank.role,
                 json.dumps([q.model_dump(mode="json") for q in bank.questions]),
                 bank.created_at or datetime.now(timezone.utc)))
        self._run(_do, commit=True)
        return bank

    def _bank_from_row(self, row) -> QuestionBank:
        questions = [Question(**q) for q in json.loads(row["questions_json"])]
        return QuestionBank(
            id=row["id"], name=row["name"], role=row["role"],
            questions=questions,
            created_at=row["created_at"],
        )

    def get_bank(self, bank_id: str) -> Optional[QuestionBank]:
        def _do(cur):
            cur.execute("SELECT * FROM question_banks WHERE id = %s", (bank_id,))
            row = cur.fetchone()
            return self._bank_from_row(row) if row else None
        return self._run(_do)

    def list_banks(self) -> list[QuestionBank]:
        def _do(cur):
            cur.execute("SELECT * FROM question_banks ORDER BY created_at DESC")
            return [self._bank_from_row(r) for r in cur.fetchall()]
        return self._run(_do)

    # ── Sessions ──────────────────────────────────────────────────────────────

    def _session_from_row(self, row) -> Session:
        answers = [AnswerEntry(**a) for a in json.loads(row["answers_json"])]
        return Session(
            id=row["id"], bank_id=row["bank_id"],
            candidate_name=row["candidate_name"], candidate_role=row["candidate_role"],
            candidate_email=row["candidate_email"],
            recruiter_email=row["recruiter_email"],
            status=SessionStatus(row["status"]),
            current_question_index=row["current_question_index"],
            answers=answers,
            started_at=row["started_at"],
            completed_at=row["completed_at"],
        )

    def save_session(self, session: Session) -> Session:
        def _do(cur):
            cur.execute("""
                INSERT INTO sessions
                (id, bank_id, candidate_name, candidate_role, candidate_email, recruiter_email,
                 status, current_question_index, answers_json, started_at, completed_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (id) DO UPDATE SET
                    bank_id = EXCLUDED.bank_id,
                    candidate_name = EXCLUDED.candidate_name,
                    candidate_role = EXCLUDED.candidate_role,
                    candidate_email = EXCLUDED.candidate_email,
                    recruiter_email = EXCLUDED.recruiter_email,
                    status = EXCLUDED.status,
                    current_question_index = EXCLUDED.current_question_index,
                    answers_json = EXCLUDED.answers_json,
                    started_at = EXCLUDED.started_at,
                    completed_at = EXCLUDED.completed_at
            """, (
                session.id, session.bank_id, session.candidate_name, session.candidate_role,
                session.candidate_email, session.recruiter_email,
                session.status.value, session.current_question_index,
                json.dumps([a.model_dump(mode="json") for a in session.answers]),
                session.started_at, session.completed_at,
            ))
        self._run(_do, commit=True)
        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        def _do(cur):
            cur.execute("SELECT * FROM sessions WHERE id = %s", (session_id,))
            row = cur.fetchone()
            return self._session_from_row(row) if row else None
        return self._run(_do)

    def list_sessions(self) -> list[Session]:
        def _do(cur):
            cur.execute("SELECT * FROM sessions ORDER BY id")
            return [self._session_from_row(r) for r in cur.fetchall()]
        return self._run(_do)

    # ── Reports ───────────────────────────────────────────────────────────────

    def save_report(self, report: EvaluationReport) -> EvaluationReport:
        def _do(cur):
            cur.execute("""
                INSERT INTO evaluation_reports (session_id, report_json)
                VALUES (%s, %s)
                ON CONFLICT (session_id) DO UPDATE SET report_json = EXCLUDED.report_json
            """, (report.session_id, report.model_dump_json()))
        self._run(_do, commit=True)
        return report

    def get_report(self, session_id: str) -> Optional[EvaluationReport]:
        def _do(cur):
            cur.execute("SELECT report_json FROM evaluation_reports WHERE session_id = %s", (session_id,))
            row = cur.fetchone()
            return EvaluationReport.model_validate_json(row["report_json"]) if row else None
        return self._run(_do)

    # ── Scheduled Interviews ──────────────────────────────────────────────────

    def _scheduled_from_row(self, row) -> ScheduledInterview:
        return ScheduledInterview(
            id=row["id"], token=row["token"], bank_id=row["bank_id"],
            candidate_name=row["candidate_name"], candidate_email=row["candidate_email"],
            candidate_role=row["candidate_role"],
            scheduled_at=row["scheduled_at"],
            recruiter_email=row["recruiter_email"],
            interviewer_name=row["interviewer_name"], company_name=row["company_name"],
            notes=row["notes"],
            is_immediate=row["is_immediate"],
            link_expires_at=row["link_expires_at"],
            status=ScheduledStatus(row["status"]), session_id=row["session_id"],
            created_at=row["created_at"],
        )

    def save_scheduled(self, s: ScheduledInterview) -> ScheduledInterview:
        def _do(cur):
            cur.execute("""
                INSERT INTO scheduled_interviews
                (id, token, bank_id, candidate_name, candidate_email, candidate_role, scheduled_at,
                 recruiter_email, interviewer_name, company_name, notes, is_immediate,
                 link_expires_at, status, session_id, created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (id) DO UPDATE SET
                    token = EXCLUDED.token,
                    bank_id = EXCLUDED.bank_id,
                    candidate_name = EXCLUDED.candidate_name,
                    candidate_email = EXCLUDED.candidate_email,
                    candidate_role = EXCLUDED.candidate_role,
                    scheduled_at = EXCLUDED.scheduled_at,
                    recruiter_email = EXCLUDED.recruiter_email,
                    interviewer_name = EXCLUDED.interviewer_name,
                    company_name = EXCLUDED.company_name,
                    notes = EXCLUDED.notes,
                    is_immediate = EXCLUDED.is_immediate,
                    link_expires_at = EXCLUDED.link_expires_at,
                    status = EXCLUDED.status,
                    session_id = EXCLUDED.session_id,
                    created_at = EXCLUDED.created_at
            """, (
                s.id, s.token, s.bank_id, s.candidate_name, s.candidate_email,
                s.candidate_role, s.scheduled_at, s.recruiter_email,
                s.interviewer_name, s.company_name, s.notes,
                s.is_immediate,
                s.link_expires_at, s.status.value, s.session_id,
                s.created_at or datetime.now(timezone.utc),
            ))
        self._run(_do, commit=True)
        return s

    def get_scheduled(self, sid: str) -> Optional[ScheduledInterview]:
        def _do(cur):
            cur.execute("SELECT * FROM scheduled_interviews WHERE id = %s", (sid,))
            row = cur.fetchone()
            return self._scheduled_from_row(row) if row else None
        return self._run(_do)

    def get_scheduled_by_token(self, token: str) -> Optional[ScheduledInterview]:
        def _do(cur):
            cur.execute("SELECT * FROM scheduled_interviews WHERE token = %s", (token,))
            row = cur.fetchone()
            return self._scheduled_from_row(row) if row else None
        return self._run(_do)

    def get_scheduled_by_session(self, session_id: str) -> Optional[ScheduledInterview]:
        def _do(cur):
            cur.execute("SELECT * FROM scheduled_interviews WHERE session_id = %s", (session_id,))
            row = cur.fetchone()
            return self._scheduled_from_row(row) if row else None
        return self._run(_do)

    def list_scheduled(self) -> list[ScheduledInterview]:
        def _do(cur):
            cur.execute("SELECT * FROM scheduled_interviews ORDER BY scheduled_at DESC")
            return [self._scheduled_from_row(r) for r in cur.fetchall()]
        return self._run(_do)
