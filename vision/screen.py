"""
Screen capture, on-demand only — never polled continuously (spec
requirement: "Do NOT continuously send screenshots to an AI model. Only
capture/process the screen when a command actually requires visual
understanding.").
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path

CAPTURE_DIR = Path("data/screen_captures")


async def capture_screen() -> Path:
    def _do() -> Path:
        import mss

        CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
        path = CAPTURE_DIR / f"capture_{datetime.now():%Y%m%d_%H%M%S}.png"
        with mss.mss() as sct:
            sct.shot(output=str(path))
        return path

    return await asyncio.to_thread(_do)
