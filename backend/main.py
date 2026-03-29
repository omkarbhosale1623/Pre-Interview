"""
main.py — Pre-Interview AI application entry point.

Fixes applied:
  * Whisper STT model is pre-warmed at startup so the first transcription
    request doesn't incur a 5-8 second model-load freeze.
  * Startup log now shows the active fallback model list.
"""
import logging
import sys
import asyncio

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import settings
from routers import auth, evaluation, interview, questions, report, scheduling
import routers.speech as _speech_router

# ── Centralised logging ──────────────────────────────────────────────────────
LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)-30s | %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    datefmt=LOG_DATE_FORMAT,
    handlers=[logging.StreamHandler(sys.stdout)],
)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("faster_whisper").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Pre-Interview AI",
    description="AI-powered voice interview platform for modern recruiters",
    version="2.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Global exception handler ─────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(
        "Unhandled exception on %s %s: %s",
        request.method, request.url.path, exc, exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Please try again."},
    )


# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(questions.router)
app.include_router(interview.router)
app.include_router(evaluation.router)
app.include_router(report.router)
app.include_router(scheduling.router)
app.include_router(_speech_router.router)


# ── Root / Health ─────────────────────────────────────────────────────────────
@app.get("/")
async def root():
    return {"name": "Pre-Interview AI", "version": "2.1.0", "docs": "/docs"}


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "llm_configured": bool(settings.llm_api_key),
        "tts_configured": bool(settings.elevenlabs_api_key),
        "email_configured": bool(settings.smtp_username and settings.smtp_password),
    }


# ── Startup ───────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def _startup():
    logger.info("═" * 60)
    logger.info("Pre-Interview AI v2.1.0 starting up")
    logger.info("LLM API key       : %s", "configured" if settings.llm_api_key else "NOT SET")
    logger.info("LLM model         : %s", settings.llm_model)
    logger.info("LLM fallbacks     : %s", settings.llm_fallback_models)
    logger.info("ElevenLabs TTS    : %s", "configured" if settings.elevenlabs_api_key else "NOT SET")
    logger.info("SMTP email        : %s", "configured" if settings.smtp_username else "NOT SET")
    logger.info("CORS origins      : %s", settings.cors_origins)
    logger.info("═" * 60)

    # Pre-warm Whisper in a background thread so the first candidate
    # transcription request doesn't freeze for 5-8 seconds.
    asyncio.create_task(_prewarm_whisper())


async def _prewarm_whisper():
    """Load the Whisper model eagerly at startup (non-blocking)."""
    try:
        import asyncio as _asyncio
        from services.speech_service import _load_whisper
        await _asyncio.to_thread(_load_whisper)
        logger.info("Whisper model pre-warmed ✓")
    except Exception as exc:
        logger.warning("Whisper pre-warm failed (will load on first request): %s", exc)
