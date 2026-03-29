"""
services/sqlite_store.py — SQLite persistence. Now includes recruiter auth + link expiry.
"""
from __future__ import annotations
import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from config import settings
from models.schemas import (
    AnswerEntry, EvaluationReport, Question, QuestionBank,
    Recruiter, RecruiterPublic, ScheduledInterview, ScheduledStatus,
    Session, SessionStatus,
)


def _db_path() -> str:
    url = settings.database_url
    path = url.replace("sqlite:///", "", 1)
    p = Path(path)
    if not p.is_absolute():
        backend_dir = Path(__file__).resolve().parent.parent
        path = str((backend_dir / p).resolve())
    return path


def _init_db(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS recruiters (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT NOT NULL,
            company_name TEXT,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS recruiter_sessions (
            token TEXT PRIMARY KEY,
            recruiter_id TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            FOREIGN KEY(recruiter_id) REFERENCES recruiters(id)
        );
        CREATE TABLE IF NOT EXISTS question_banks (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            role TEXT,
            questions_json TEXT NOT NULL,
            created_at TEXT NOT NULL
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
            started_at TEXT,
            completed_at TEXT
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
            scheduled_at TEXT NOT NULL,
            recruiter_email TEXT NOT NULL,
            interviewer_name TEXT,
            company_name TEXT,
            notes TEXT,
            is_immediate INTEGER NOT NULL DEFAULT 0,
            link_expires_at TEXT,
            status TEXT NOT NULL,
            session_id TEXT,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_scheduled_token ON scheduled_interviews(token);
        CREATE INDEX IF NOT EXISTS idx_recruiter_email ON recruiters(email);
    """)


def _conn():
    path = _db_path()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    _init_db(conn)
    return conn


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def _dt_iso(d: Optional[datetime]) -> Optional[str]:
    return d.isoformat() if d else None


def _parse_dt(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def _bank_from_row(row: sqlite3.Row) -> QuestionBank:
    questions = [Question(**q) for q in json.loads(row["questions_json"])]
    return QuestionBank(
        id=row["id"], name=row["name"], role=row["role"],
        questions=questions,
        created_at=_parse_dt(row["created_at"]) or datetime.utcnow(),
    )


def _session_from_row(row: sqlite3.Row) -> Session:
    answers = [AnswerEntry(**a) for a in json.loads(row["answers_json"])]
    return Session(
        id=row["id"], bank_id=row["bank_id"],
        candidate_name=row["candidate_name"], candidate_role=row["candidate_role"],
        candidate_email=row["candidate_email"] if "candidate_email" in row.keys() else None,
        recruiter_email=row["recruiter_email"] if "recruiter_email" in row.keys() else None,
        status=SessionStatus(row["status"]),
        current_question_index=row["current_question_index"],
        answers=answers,
        started_at=_parse_dt(row["started_at"]),
        completed_at=_parse_dt(row["completed_at"]),
    )


def _scheduled_from_row(row: sqlite3.Row) -> ScheduledInterview:
    keys = row.keys()
    return ScheduledInterview(
        id=row["id"], token=row["token"], bank_id=row["bank_id"],
        candidate_name=row["candidate_name"], candidate_email=row["candidate_email"],
        candidate_role=row["candidate_role"],
        scheduled_at=datetime.fromisoformat(row["scheduled_at"].replace("Z", "+00:00")),
        recruiter_email=row["recruiter_email"] if "recruiter_email" in keys else "",
        interviewer_name=row["interviewer_name"], company_name=row["company_name"],
        notes=row["notes"],
        is_immediate=bool(row["is_immediate"]) if "is_immediate" in keys else False,
        link_expires_at=_parse_dt(row["link_expires_at"]) if "link_expires_at" in keys else None,
        status=ScheduledStatus(row["status"]), session_id=row["session_id"],
        created_at=_parse_dt(row["created_at"]) or datetime.utcnow(),
    )


class SQLiteStore:
    def _run(self, fn, commit=False):
        conn = _conn()
        try:
            result = fn(conn)
            if commit:
                conn.commit()
            return result
        finally:
            conn.close()

    # ── Recruiter Auth ────────────────────────────────────────────────────────

    def create_recruiter(self, email: str, password: str, full_name: str, company_name: Optional[str]) -> Optional[Recruiter]:
        """Create a new recruiter. Returns None if email already exists."""
        def _do(c):
            existing = c.execute("SELECT id FROM recruiters WHERE email = ?", (email.lower(),)).fetchone()
            if existing:
                return None
            rec = Recruiter(
                email=email.lower(), password_hash=_hash_password(password),
                full_name=full_name, company_name=company_name,
            )
            c.execute(
                "INSERT INTO recruiters (id, email, password_hash, full_name, company_name, created_at) VALUES (?,?,?,?,?,?)",
                (rec.id, rec.email, rec.password_hash, rec.full_name, rec.company_name, _dt_iso(rec.created_at)),
            )
            return rec
        return self._run(_do, commit=True)

    def authenticate_recruiter(self, email: str, password: str) -> Optional[RecruiterPublic]:
        """Validate credentials. Returns public recruiter if valid."""
        def _do(c):
            row = c.execute("SELECT * FROM recruiters WHERE email = ?", (email.lower(),)).fetchone()
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
        """Create a session token."""
        from datetime import timedelta
        token = str(uuid.uuid4())
        expires = datetime.utcnow() + timedelta(hours=expire_hours)
        def _do(c):
            c.execute(
                "INSERT INTO recruiter_sessions (token, recruiter_id, expires_at) VALUES (?,?,?)",
                (token, recruiter_id, expires.isoformat()),
            )
        self._run(_do, commit=True)
        return token

    def get_recruiter_by_token(self, token: str) -> Optional[RecruiterPublic]:
        """Look up recruiter from session token."""
        def _do(c):
            row = c.execute("""
                SELECT r.id, r.email, r.full_name, r.company_name, rs.expires_at
                FROM recruiter_sessions rs
                JOIN recruiters r ON r.id = rs.recruiter_id
                WHERE rs.token = ?
            """, (token,)).fetchone()
            if not row:
                return None
            expires = _parse_dt(row["expires_at"])
            if expires and expires < datetime.utcnow():
                return None
            return RecruiterPublic(
                id=row["id"], email=row["email"],
                full_name=row["full_name"], company_name=row["company_name"],
            )
        return self._run(_do)

    def delete_recruiter_session(self, token: str) -> None:
        def _do(c):
            c.execute("DELETE FROM recruiter_sessions WHERE token = ?", (token,))
        self._run(_do, commit=True)

    # ── Question Banks ────────────────────────────────────────────────────────

    def save_bank(self, bank: QuestionBank) -> QuestionBank:
        def _do(c):
            c.execute(
                "INSERT OR REPLACE INTO question_banks (id, name, role, questions_json, created_at) VALUES (?,?,?,?,?)",
                (bank.id, bank.name, bank.role,
                 json.dumps([q.model_dump(mode="json") for q in bank.questions]),
                 _dt_iso(bank.created_at) or datetime.utcnow().isoformat()),
            )
        self._run(_do, commit=True)
        return bank

    def get_bank(self, bank_id: str) -> Optional[QuestionBank]:
        return self._run(lambda c: (
            _bank_from_row(r) if (r := c.execute("SELECT * FROM question_banks WHERE id=?", (bank_id,)).fetchone()) else None
        ))

    def list_banks(self) -> list[QuestionBank]:
        return self._run(lambda c: [
            _bank_from_row(r) for r in c.execute("SELECT * FROM question_banks ORDER BY created_at DESC").fetchall()
        ])

    # ── Sessions ──────────────────────────────────────────────────────────────

    def save_session(self, session: Session) -> Session:
        def _do(c):
            c.execute("""
                INSERT OR REPLACE INTO sessions
                (id, bank_id, candidate_name, candidate_role, candidate_email, recruiter_email,
                 status, current_question_index, answers_json, started_at, completed_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, (
                session.id, session.bank_id, session.candidate_name, session.candidate_role,
                session.candidate_email, session.recruiter_email,
                session.status.value, session.current_question_index,
                json.dumps([a.model_dump(mode="json") for a in session.answers]),
                _dt_iso(session.started_at), _dt_iso(session.completed_at),
            ))
        self._run(_do, commit=True)
        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        return self._run(lambda c: (
            _session_from_row(r) if (r := c.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()) else None
        ))

    def list_sessions(self) -> list[Session]:
        return self._run(lambda c: [
            _session_from_row(r) for r in c.execute("SELECT * FROM sessions ORDER BY id").fetchall()
        ])

    # ── Reports ───────────────────────────────────────────────────────────────

    def save_report(self, report: EvaluationReport) -> EvaluationReport:
        def _do(c):
            c.execute(
                "INSERT OR REPLACE INTO evaluation_reports (session_id, report_json) VALUES (?,?)",
                (report.session_id, report.model_dump_json()),
            )
        self._run(_do, commit=True)
        return report

    def get_report(self, session_id: str) -> Optional[EvaluationReport]:
        def _do(c):
            r = c.execute("SELECT report_json FROM evaluation_reports WHERE session_id=?", (session_id,)).fetchone()
            return EvaluationReport.model_validate_json(r["report_json"]) if r else None
        return self._run(_do)

    # ── Scheduled Interviews ──────────────────────────────────────────────────

    def save_scheduled(self, s: ScheduledInterview) -> ScheduledInterview:
        def _do(c):
            c.execute("""
                INSERT OR REPLACE INTO scheduled_interviews
                (id, token, bank_id, candidate_name, candidate_email, candidate_role, scheduled_at,
                 recruiter_email, interviewer_name, company_name, notes, is_immediate,
                 link_expires_at, status, session_id, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                s.id, s.token, s.bank_id, s.candidate_name, s.candidate_email,
                s.candidate_role, s.scheduled_at.isoformat(), s.recruiter_email,
                s.interviewer_name, s.company_name, s.notes,
                1 if s.is_immediate else 0,
                _dt_iso(s.link_expires_at), s.status.value, s.session_id,
                _dt_iso(s.created_at) or datetime.utcnow().isoformat(),
            ))
        self._run(_do, commit=True)
        return s

    def get_scheduled(self, sid: str) -> Optional[ScheduledInterview]:
        return self._run(lambda c: (
            _scheduled_from_row(r) if (r := c.execute("SELECT * FROM scheduled_interviews WHERE id=?", (sid,)).fetchone()) else None
        ))

    def get_scheduled_by_token(self, token: str) -> Optional[ScheduledInterview]:
        return self._run(lambda c: (
            _scheduled_from_row(r) if (r := c.execute("SELECT * FROM scheduled_interviews WHERE token=?", (token,)).fetchone()) else None
        ))

    def get_scheduled_by_session(self, session_id: str) -> Optional[ScheduledInterview]:
        return self._run(lambda c: (
            _scheduled_from_row(r) if (r := c.execute("SELECT * FROM scheduled_interviews WHERE session_id=?", (session_id,)).fetchone()) else None
        ))

    def list_scheduled(self) -> list[ScheduledInterview]:
        return self._run(lambda c: [
            _scheduled_from_row(r) for r in c.execute("SELECT * FROM scheduled_interviews ORDER BY scheduled_at DESC").fetchall()
        ])


store = SQLiteStore()
