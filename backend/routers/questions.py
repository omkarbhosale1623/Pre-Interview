"""
routers/questions.py — Upload and retrieve question banks.

Endpoints:
  POST /questions/upload        — upload CSV, JSON, TXT, or DOCX file
  GET  /questions/banks         — list all uploaded banks
  GET  /questions/banks/{id}    — get a specific bank
"""
import logging

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from models.schemas import QuestionBank
from services.question_service import parse_question_bank
from services.session_store import store

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/questions", tags=["Question Banks"])


@router.post("/upload", response_model=QuestionBank)
async def upload_question_bank(
    file: UploadFile = File(..., description="CSV, JSON, TXT or DOCX question bank file"),
    bank_name: str = Form(..., description="Friendly name for this question bank"),
    role: str = Form(None, description="Target role (optional)"),
):
    """Upload a question bank file and persist it."""
    try:
        content = await file.read()
    except Exception as exc:
        logger.error("Failed to read uploaded file: %s", exc, exc_info=True)
        raise HTTPException(status_code=400, detail="Failed to read uploaded file.")

    try:
        bank = parse_question_bank(
            content=content,
            filename=file.filename or "upload",
            bank_name=bank_name,
            role=role,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.error("Unexpected parse error for '%s': %s", file.filename, exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to parse question bank.")

    try:
        store.save_bank(bank)
    except Exception as exc:
        logger.error("Failed to save bank '%s': %s", bank_name, exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to save question bank.")

    logger.info("Bank uploaded: '%s' (%d questions, id=%s)", bank.name, len(bank.questions), bank.id)
    return bank


@router.get("/banks", response_model=list[QuestionBank])
async def list_banks():
    """Return all uploaded question banks."""
    try:
        return store.list_banks()
    except Exception as exc:
        logger.error("Failed to list banks: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list question banks.")


@router.get("/banks/{bank_id}", response_model=QuestionBank)
async def get_bank(bank_id: str):
    """Retrieve a single question bank by ID."""
    try:
        bank = store.get_bank(bank_id)
    except Exception as exc:
        logger.error("Failed to fetch bank %s: %s", bank_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch question bank.")
    if not bank:
        raise HTTPException(status_code=404, detail="Question bank not found")
    return bank
