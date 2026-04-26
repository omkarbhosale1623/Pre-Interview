"""
config.py — App-wide settings loaded from environment variables.

Model notes (as of March 2026):
  * deepseek/deepseek-r1:free  → broken/404 on OpenRouter, removed from defaults
  * google/gemini-2.5-flash    → fast, free tier available, good quality
  * meta-llama/llama-3.3-70b-instruct → reliable, high quality
  * meta-llama/llama-3.1-8b-instruct:free → free, lower quality but works
"""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = str((Path(__file__).parent / ".env").resolve())


class Settings(BaseSettings):
    # ── OpenRouter (LLM) ──────────────────────────────────────────────────────
    llm_api_key: str = ""
    # Primary model — can be overridden in .env (LLM_MODEL=...)
    llm_model: str = "google/gemini-2.5-flash"
    # Fallback chain tried in order when primary fails
    llm_fallback_models: list[str] = [
        "google/gemini-2.5-flash",
        "meta-llama/llama-3.3-70b-instruct",
        "meta-llama/llama-3.1-8b-instruct:free",
        "deepseek/deepseek-chat",
    ]
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_site_url: str = "https://preinterviewai.com"
    openrouter_site_name: str = "Pre-Interview AI"

    # ── Recruiter Auth ────────────────────────────────────────────────────────
    jwt_secret: str = "0dPks88NbLgXNQorlnH_Ltkm5n0dL_klNH4ofo6YXeLHVb9A2j3JfR6Sy6U6k2pkT7cdzeUzncQDNu3NcAxIUg"
    session_expire_hours: int = 72

    # ── CORS ────────────────────────────────────────────────────────────
    cors_origins: list[str] = ["https://preinterview-frontend.s3-website.eu-north-1.amazonaws.com"]

    # ── App URL ───────────────────────────────────────────────────────────
    app_base_url: str = "https://preinterview-frontend.s3-website.eu-north-1.amazonaws.com"

    # ── SMTP ────────────────────────────────────────────────────────────
    smtp_server: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    email_from: str = ""

    # ── ElevenLabs TTS ────────────────────────────────────────────────────────
    elevenlabs_api_key: str = ""

    # ── SQLite ──────���─────────────────────────────────────────────────────
   # database_url: str = "sqlite:///./preinterviewai.db"

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


settings = Settings()
