"""
The `read_screen` tool: capture the screen, run OCR, hand the extracted
text to the brain to summarize/answer from — NOT read the raw OCR dump
aloud (that would be a wall of garbled text). This module only does the
capture+extract step; the brain composes the actual spoken answer from
the tool result, same as any other tool.

Tries capturing just the active window's region first (faster, and more
relevant to what's actually being asked — see vision/screen.py), falling
back to a full-screen capture if that's not available.
"""
from __future__ import annotations

import time

from core.errors import JarvisError
from core.logging_setup import log
from vision.ocr import extract_text
from vision.screen import capture_active_window_region, capture_screen

MAX_CHARS_RETURNED = 4000  # keep the tool result bounded — OCR on a busy
                           # screen can produce a lot of noisy text


async def read_screen() -> str:
    t0 = time.monotonic()

    path = await capture_active_window_region()
    if path is None:
        path = await capture_screen()

    text = await extract_text(path)
    log.info("[read_screen] total end-to-end: %.0fms", (time.monotonic() - t0) * 1000)

    text = text.strip()
    if not text:
        raise JarvisError("I couldn't find any readable text on the screen right now.")
    if len(text) > MAX_CHARS_RETURNED:
        text = text[:MAX_CHARS_RETURNED] + "... (truncated)"
    return text
