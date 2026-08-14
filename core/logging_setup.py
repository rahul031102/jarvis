"""
Structured, human-readable logging. Two streams:
- console: short, timestamped, useful lines only (what the user sees in dev)
- file: full detail including tracebacks (what you debug from)

Nothing user-facing ever sees a raw traceback — see core/errors.py.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

from config.settings import settings

_LOG_FORMAT_CONSOLE = "[%(asctime)s] %(message)s"
_LOG_FORMAT_FILE = "[%(asctime)s] %(levelname)s %(name)s: %(message)s"
_DATE_FMT = "%H:%M:%S"


def setup_logging() -> logging.Logger:
    logger = logging.getLogger("jarvis")
    if logger.handlers:
        return logger  # already configured

    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logger.setLevel(level)

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(logging.Formatter(_LOG_FORMAT_CONSOLE, _DATE_FMT))
    console.setLevel(level)
    logger.addHandler(console)

    log_path = Path(settings.log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(_LOG_FORMAT_FILE, _DATE_FMT))
    file_handler.setLevel(logging.DEBUG)
    logger.addHandler(file_handler)

    return logger


log = setup_logging()
