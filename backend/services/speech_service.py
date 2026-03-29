"""
services/speech_service.py — STT (Faster-Whisper) + TTS (ElevenLabs primary, OpenAI fallback).

Architecture:
    STT: Faster-Whisper model loaded lazily, ffmpeg used for audio conversion.
    TTS: ElevenLabs is the PRIMARY provider. OpenAI TTS-1 is the FALLBACK.
         Results are cached in-memory (max 100 entries) to avoid re-synthesis.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Dict

from config import settings

logger = logging.getLogger(__name__)

# ── OpenAI client (TTS fallback only) ─────────────────────────────────────────
_openai_client = None
try:
    from openai import OpenAI
    _openai_api_key = os.getenv("OPENAI_API_KEY")
    if _openai_api_key:
        _openai_client = OpenAI(api_key=_openai_api_key)
        logger.info("OpenAI TTS fallback client initialised")
    else:
        logger.info("OPENAI_API_KEY not set — OpenAI TTS fallback disabled")
except ImportError:
    logger.warning("openai package not installed — OpenAI TTS fallback unavailable")

# ── TTS cache ─────────────────────────────────────────────────────────────────
_TTS_CACHE_MAX = 100
_tts_cache: dict[str, Dict] = {}

# ── Whisper STT ───────────────────────────────────────────────────────────────
_whisper_model = None


def _load_whisper():
    """Lazily load the Faster-Whisper model."""
    global _whisper_model
    if _whisper_model is not None:
        return _whisper_model

    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        logger.error("faster-whisper not installed")
        raise RuntimeError("faster-whisper not installed. Run: pip install faster-whisper") from exc

    try:
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        device = "cpu"

    compute_type = "float16" if device == "cuda" else "float32"
    logger.info("Loading Whisper 'small' on %s / %s", device, compute_type)

    try:
        _whisper_model = WhisperModel("small", device=device, compute_type=compute_type)
        logger.info("Whisper model loaded successfully")
    except Exception as exc:
        logger.error("Failed to load Whisper model: %s", exc, exc_info=True)
        raise RuntimeError(f"Whisper model load failed: {exc}") from exc

    return _whisper_model


def _find_ffmpeg() -> str | None:
    """Find ffmpeg in PATH or common Windows install locations."""
    import shutil
    if exe := shutil.which("ffmpeg"):
        return exe
    for candidate in [
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
        r"C:\Users\omkar\ffmpeg\bin\ffmpeg.exe",
    ]:
        if Path(candidate).exists():
            return candidate
    return None


def _to_wav(data: bytes, src_fmt: str) -> bytes:
    """Convert audio bytes to WAV 16kHz mono using ffmpeg if available."""
    src_fmt = src_fmt.lower().strip(".")
    if src_fmt in ("wav", "wave"):
        return data

    ffmpeg = _find_ffmpeg()
    if not ffmpeg:
        logger.warning(
            "ffmpeg not found — passing raw %s bytes directly to Whisper. "
            "Install ffmpeg for reliable browser WebM/Ogg support.",
            src_fmt,
        )
        return data

    inp_path = None
    out_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=f".{src_fmt}", delete=False) as inp:
            inp.write(data)
            inp_path = inp.name
        out_path = inp_path.replace(f".{src_fmt}", ".wav")

        result = subprocess.run(
            [ffmpeg, "-y", "-i", inp_path,
             "-ar", "16000", "-ac", "1", "-sample_fmt", "s16", out_path],
            capture_output=True, timeout=30,
        )
        if result.returncode != 0:
            logger.warning("ffmpeg conversion failed: %s", result.stderr.decode(errors="replace"))
            return data
        return Path(out_path).read_bytes()

    except subprocess.TimeoutExpired:
        logger.error("ffmpeg conversion timed out (30s)")
        return data
    except Exception as exc:
        logger.error("ffmpeg error: %s", exc, exc_info=True)
        return data
    finally:
        for p in (inp_path, out_path):
            if p:
                try:
                    os.unlink(p)
                except OSError:
                    pass


def transcribe_audio_bytes(data: bytes, fmt: str = "webm") -> str:
    """
    Transcribe audio bytes using Faster-Whisper.

    Returns the transcribed text, or empty string if audio is too small.
    """
    if not data or len(data) < 100:
        logger.debug("Audio blob too small (%d bytes), returning empty", len(data) if data else 0)
        return ""

    model = _load_whisper()
    wav_data = _to_wav(data, fmt or "webm")
    ext = "wav" if wav_data is not data else (fmt or "webm")

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp:
            tmp.write(wav_data)
            tmp_path = tmp.name

        segments_generator, info = model.transcribe(
            tmp_path,
            language="en",
            beam_size=5,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500},
        )
        # Must consume the lazy generator
        text = " ".join(seg.text for seg in segments_generator).strip()
        logger.info("Transcribed [lang=%s, %.1fs]: '%s'", info.language, info.duration, text[:100])
        return text

    except Exception as exc:
        logger.error("Whisper transcription error: %s", exc, exc_info=True)
        raise RuntimeError(f"Transcription failed: {exc}") from exc
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


# ── TTS: ElevenLabs (PRIMARY) ─────────────────────────────────────────────────

def _synthesize_elevenlabs(text: str) -> bytes:
    """Synthesize speech using ElevenLabs TTS (primary provider)."""
    if not settings.elevenlabs_api_key:
        raise ValueError("ElevenLabs API key not configured")

    try:
        from elevenlabs import ElevenLabs
    except ImportError as exc:
        raise RuntimeError("elevenlabs package not installed. Run: pip install elevenlabs") from exc

    try:
        client = ElevenLabs(api_key=settings.elevenlabs_api_key)
        voice_id = "EXAVITQu4vr4xnSDxMaL"  # Bella voice

        response = client.text_to_speech.convert(
            voice_id=voice_id,
            text=text,
            model_id="eleven_turbo_v2",
            output_format="mp3_22050_32",
        )

        # Collect streaming response into bytes
        audio_chunks = []
        for chunk in response:
            audio_chunks.append(chunk)
        audio_bytes = b"".join(audio_chunks)

        if not audio_bytes:
            raise RuntimeError("ElevenLabs returned empty audio")

        logger.info("ElevenLabs TTS: %d bytes for %d chars", len(audio_bytes), len(text))
        return audio_bytes

    except Exception as exc:
        logger.warning("ElevenLabs TTS failed: %s", exc)
        raise


async def _synthesize_elevenlabs_async(text: str) -> bytes:
    """Async wrapper for ElevenLabs TTS."""
    return await asyncio.to_thread(_synthesize_elevenlabs, text)


# ── TTS: OpenAI (FALLBACK) ───────────────────────────────────────────────────

def _synthesize_openai(text: str) -> bytes:
    """Synthesize speech using OpenAI TTS-1 (fallback provider)."""
    if not _openai_client:
        raise ValueError("OpenAI client not available — OPENAI_API_KEY not set or openai not installed")

    try:
        response = _openai_client.audio.speech.create(
            model="tts-1",
            voice="alloy",
            input=text,
        )
        audio_bytes = response.content

        if not audio_bytes:
            raise RuntimeError("OpenAI TTS returned empty audio")

        logger.info("OpenAI TTS (fallback): %d bytes for %d chars", len(audio_bytes), len(text))
        return audio_bytes

    except Exception as exc:
        logger.warning("OpenAI TTS failed: %s", exc)
        raise


async def _synthesize_openai_async(text: str) -> bytes:
    """Async wrapper for OpenAI TTS."""
    return await asyncio.to_thread(_synthesize_openai, text)


# ── Public TTS API ────────────────────────────────────────────────────────────

def synthesize(text: str) -> Dict:
    """
    Synthesize text to speech.
    Chain: ElevenLabs (primary) → OpenAI (fallback) → empty audio (last resort).

    Returns: { "wav": bytes, "rate": int }
    """
    # Try ElevenLabs first (PRIMARY)
    try:
        audio_bytes = _synthesize_elevenlabs(text)
        return {"rate": 22050, "wav": audio_bytes}
    except Exception as e1:
        logger.warning("Primary TTS (ElevenLabs) failed, trying fallback: %s", e1)

    # Try OpenAI (FALLBACK)
    try:
        audio_bytes = _synthesize_openai(text)
        return {"rate": 24000, "wav": audio_bytes}
    except Exception as e2:
        logger.error("Fallback TTS (OpenAI) also failed: %s", e2)

    # Last resort — empty audio
    logger.error("All TTS services failed. Returning empty audio.")
    return {"rate": 24000, "wav": b""}


async def synthesize_async(text: str) -> Dict:
    """
    Async version: Synthesize text to speech with caching.
    Chain: Cache → ElevenLabs (primary) → OpenAI (fallback) → empty audio.

    Returns: { "wav": bytes, "rate": int }
    """
    # Check cache first
    cache_key = hashlib.md5(text.encode()).hexdigest()
    if cache_key in _tts_cache:
        logger.debug("TTS cache hit for key %s", cache_key[:8])
        return _tts_cache[cache_key]

    # Try ElevenLabs (PRIMARY)
    try:
        audio_bytes = await _synthesize_elevenlabs_async(text)
        result = {"rate": 22050, "wav": audio_bytes}
    except Exception as e1:
        logger.warning("Primary TTS (ElevenLabs) failed, trying fallback: %s", e1)

        # Try OpenAI (FALLBACK)
        try:
            audio_bytes = await _synthesize_openai_async(text)
            result = {"rate": 24000, "wav": audio_bytes}
        except Exception as e2:
            logger.error("Fallback TTS (OpenAI) also failed: %s", e2)
            return {"rate": 24000, "wav": b""}

    # Cache the result (limit cache size to prevent memory issues)
    if len(_tts_cache) < _TTS_CACHE_MAX:
        _tts_cache[cache_key] = result
    else:
        logger.debug("TTS cache full (%d entries), skipping cache", len(_tts_cache))

    return result
