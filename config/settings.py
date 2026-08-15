"""
Centralized configuration. Every tunable value in the whole app is loaded
here, once, from environment variables. Nothing else in the codebase should
call os.getenv directly — import Settings instead.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")


def _bool(val: str | None, default: bool = False) -> bool:
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Settings:
    # LLM (Groq — OpenAI-compatible API, used here for fast/free testing)
    groq_api_key: str = field(default_factory=lambda: os.getenv("GROQ_API_KEY", ""))
    groq_model: str = field(default_factory=lambda: os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"))

    # STT
    stt_provider: str = field(default_factory=lambda: os.getenv("STT_PROVIDER", "local"))
    stt_model_size: str = field(default_factory=lambda: os.getenv("STT_MODEL_SIZE", "small"))
    deepgram_api_key: str = field(default_factory=lambda: os.getenv("DEEPGRAM_API_KEY", ""))

    # TTS
    tts_provider: str = field(default_factory=lambda: os.getenv("TTS_PROVIDER", "edge"))
    tts_voice: str = field(default_factory=lambda: os.getenv("TTS_VOICE", "en-US-GuyNeural"))
    elevenlabs_api_key: str = field(default_factory=lambda: os.getenv("ELEVENLABS_API_KEY", ""))
    elevenlabs_voice_id: str = field(default_factory=lambda: os.getenv("ELEVENLABS_VOICE_ID", ""))

    # Wake word
    wake_word_model: str = field(default_factory=lambda: os.getenv("WAKE_WORD_MODEL", "jarvis"))
    wake_word_threshold: float = field(default_factory=lambda: float(os.getenv("WAKE_WORD_THRESHOLD", "0.5")))

    # Browser
    default_browser: str = field(default_factory=lambda: os.getenv("DEFAULT_BROWSER", "chrome"))

    # Vision (screen awareness / OCR)
    tesseract_cmd: str = field(default_factory=lambda: os.getenv("TESSERACT_CMD", ""))

    # Project runner
    project_start_timeout_s: int = field(
        default_factory=lambda: int(os.getenv("PROJECT_START_TIMEOUT_S", "60"))
    )

    # Logging
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    log_file: str = field(default_factory=lambda: os.getenv("LOG_FILE", "logs/jarvis.log"))

    # Paths
    root_dir: Path = ROOT_DIR
    memory_db_path: Path = ROOT_DIR / "data" / "memory.db"


settings = Settings()
