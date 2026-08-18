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
        import mss.tools
        from PIL import Image

        CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
        path = CAPTURE_DIR / f"capture_{datetime.now():%Y%m%d_%H%M%S}.png"
        
        with mss.mss() as sct:
            # sct.monitors[1] is the primary screen. sct.monitors[0] is all monitors combined,
            # which slows down OCR significantly if the user has multiple displays.
            monitor = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
            sct_img = sct.grab(monitor)
            mss.tools.to_png(sct_img.rgb, sct_img.size, output=str(path))
            
        # Post-process for Tesseract speed and accuracy:
        # Convert to grayscale to reduce channels from 3 to 1 (making Tesseract 3x faster)
        # and resize to 1920px max width to keep the resolution highly performant.
        try:
            img = Image.open(path)
            max_width = 1920
            if img.width > max_width:
                w_percent = (max_width / float(img.width))
                h_size = int((float(img.height) * float(w_percent)))
                img = img.resize((max_width, h_size), Image.Resampling.LANCZOS)
            
            # Grayscale conversion is the biggest speedup for OCR
            img = img.convert("L")
            img.save(path, "PNG", optimize=True)
        except Exception:
            pass  # Fall back to raw capture if optimization fails
            
        return path

    return await asyncio.to_thread(_do)
