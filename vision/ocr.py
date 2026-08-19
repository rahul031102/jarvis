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
from core.logging_setup import log


import time

MAX_OCR_DIMENSION = 1600
TESSERACT_CONFIG = "--oem 1 --psm 11 -c load_system_dawg=0 -c load_freq_dawg=0"


def _configure_tesseract() -> None:
    import pytesseract

    if settings.tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd


def _preprocess(image):
    """Grayscale + bounded downscale. Returns a new image; never mutates
    the caller's image object."""
    image = image.convert("L")  # grayscale

    width, height = image.size
    longest_edge = max(width, height)
    if longest_edge > MAX_OCR_DIMENSION:
        from PIL import Image

        scale = MAX_OCR_DIMENSION / longest_edge
        new_size = (int(width * scale), int(height * scale))
        image = image.resize(new_size, Image.Resampling.LANCZOS)

    return image


async def extract_text(image_path: Path) -> str:
    def _do() -> str:
        import pytesseract
        from PIL import Image

        _configure_tesseract()
        try:
            t0 = time.monotonic()
            image = Image.open(image_path)
            original_size = image.size

            processed = _preprocess(image)
            t1 = time.monotonic()

            text = pytesseract.image_to_string(processed, config=TESSERACT_CONFIG)
            t2 = time.monotonic()

            log.info(
                "[ocr] size %s -> %s, preprocess=%.0fms, tesseract=%.0fms, total=%.0fms",
                original_size, processed.size, (t1 - t0) * 1000, (t2 - t1) * 1000, (t2 - t0) * 1000,
            )
            return text
        except pytesseract.TesseractNotFoundError:
            raise JarvisError(
                "I can't read the screen because Tesseract OCR isn't installed. "
                "Install it and either add it to PATH or set TESSERACT_CMD in your .env file."
            )

    return await asyncio.to_thread(_do)


async def extract_text_with_boxes(image_path: Path) -> list[dict]:
    """Like extract_text, but returns each recognized word with its pixel
    bounding box (left, top, width, height) relative to the image, instead
    of a flat string. Used when we need to click something OCR found —
    e.g. a "Copy" item in a right-click context menu — not just read text.

    If image_path came from vision.screen.capture_region(left, top, ...),
    add that region's (left, top) back to each box to get absolute screen
    coordinates for clicking."""
    def _do() -> list[dict]:
        import pytesseract
        from PIL import Image

        _configure_tesseract()
        try:
            image = Image.open(image_path)
            data = pytesseract.image_to_data(
                image, config="--oem 1 --psm 6", output_type=pytesseract.Output.DICT
            )
        except pytesseract.TesseractNotFoundError:
            raise JarvisError(
                "I can't read the screen because Tesseract OCR isn't installed. "
                "Install it and either add it to PATH or set TESSERACT_CMD in your .env file."
            )

        words = []
        for i, text in enumerate(data["text"]):
            if not text or not isinstance(text, str):
                continue
            text = text.strip()
            if not text:
                continue
            try:
                words.append({
                    "text": text,
                    "left": int(data["left"][i]),
                    "top": int(data["top"][i]),
                    "width": int(data["width"][i]),
                    "height": int(data["height"][i]),
                })
            except (ValueError, TypeError):
                continue
        return words

    return await asyncio.to_thread(_do)
