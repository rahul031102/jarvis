"""
OCR on a captured screenshot. Requires the Tesseract OCR *binary* to be
installed on the system (pytesseract is just a wrapper around it) — this
is a real external dependency, not something pip alone provides. Stated
plainly here rather than silently failing with a cryptic error, per the
"don't fake features" rule: if Tesseract isn't installed, JARVIS says so
and tells you how to fix it instead of crashing.

Install on Windows: https://github.com/UB-Mannheim/tesseract/wiki
Then either add it to PATH, or set TESSERACT_CMD in .env to the full path
of tesseract.exe.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from config.settings import settings
from core.errors import JarvisError


def _configure_tesseract() -> None:
    import pytesseract

    if settings.tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd


async def extract_text(image_path: Path) -> str:
    def _do() -> str:
        import pytesseract
        from PIL import Image

        _configure_tesseract()
        try:
            image = Image.open(image_path)
            return pytesseract.image_to_string(image)
        except pytesseract.TesseractNotFoundError:
            raise JarvisError(
                "I can't read the screen because Tesseract OCR isn't installed. "
                "Install it and either add it to PATH or set TESSERACT_CMD in your .env file."
            )

    return await asyncio.to_thread(_do)
