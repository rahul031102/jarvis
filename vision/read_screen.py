"""
The `read_screen` tool: capture the screen, run OCR, hand the extracted
text to the brain to summarize/answer from — NOT read the raw OCR dump
aloud (that would be a wall of garbled text). This module only does the
capture+extract step; the brain composes the actual spoken answer from
the tool result, same as any other tool.
"""
from __future__ import annotations

from core.errors import JarvisError
from vision.ocr import extract_text
from vision.screen import capture_screen

MAX_CHARS_RETURNED = 4000  # keep the tool result bounded — OCR on a busy
                           # screen can produce a lot of noisy text


async def read_screen() -> str:
    path = await capture_screen()
    text = await extract_text(path)
    text = text.strip()
    if not text:
        raise JarvisError("I couldn't find any readable text on the screen right now.")
    if len(text) > MAX_CHARS_RETURNED:
        text = text[:MAX_CHARS_RETURNED] + "... (truncated)"
    return text
