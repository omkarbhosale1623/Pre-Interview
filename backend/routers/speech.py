"""
routers/speech.py — Speech-related endpoints (STT/TTS).

Two endpoints are exposed:

* POST /speech/transcribe  - accepts a multipart file upload (wav/webm/ogg)
  and returns a simple JSON object `{ "text": "..." }` obtained via
  faster-whisper.
* POST /speech/tts         - accepts a form field `text` and returns an
  audio stream synthesized using ElevenLabs TTS (primary) with OpenAI TTS
  (fallback). The response can be played directly by the browser.
"""
from __future__ import annotations

import io
import logging

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse

from services import speech_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/speech", tags=["Speech"])


@router.post("/transcribe")
async def transcribe(file: UploadFile = File(...)) -> dict[str, str]:
    """Accept an audio file and return the transcription."""
    try:
        contents = await file.read()
        logger.info("Transcribe request: %d bytes, filename=%s", len(contents), file.filename)

        # attempt to guess format from filename or content type
        fmt = None
        if file.filename and "." in file.filename:
            fmt = file.filename.rsplit('.', 1)[1].lower()
        elif file.content_type:
            fmt = file.content_type.split('/')[-1]

        text = speech_service.transcribe_audio_bytes(contents, fmt=fmt or "wav")
        logger.info("Transcription result: '%s'", text[:80] if text else "(empty)")
        return {"text": text}

    except Exception as exc:
        logger.error("Transcription failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Transcription failed: {exc}")


@router.post("/tts")
async def tts(text: str = Form(...)):
    """Synthesize the provided text into an audio stream (ElevenLabs primary, OpenAI fallback)."""
    if not text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty.")

    try:
        logger.info("TTS request: %d chars", len(text))
        result = speech_service.synthesize(text)

        wav_data = result.get("wav", b"")
        if not wav_data:
            logger.warning("TTS returned empty audio for: '%s'", text[:50])

        buf = io.BytesIO(wav_data)
        buf.seek(0)
        return StreamingResponse(buf, media_type="audio/mpeg")

    except Exception as exc:
        logger.error("TTS failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"TTS failed: {exc}")
