"""
Screen capture, on-demand only — never polled continuously (spec
requirement: "Do NOT continuously send screenshots to an AI model. Only
capture/process the screen when a command actually requires visual
understanding.").
"""
from __future__ import annotations

import asyncio
import time
from datetime import datetime
from pathlib import Path

from core.logging_setup import log

CAPTURE_DIR = Path("data/screen_captures")
MIN_REGION_DIMENSION = 40


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


async def capture_region(left: int, top: int, right: int, bottom: int) -> Path:
    """Captures a specific screen rectangle (absolute screen coordinates,
    e.g. from tools.windows.get_window_rect) instead of the whole screen —
    used to OCR/click inside just one window's area.

    Caveat stated plainly: this assumes 100% display scaling. On a scaled
    display (125%/150% etc.), pywinauto's rectangle() and mss's capture
    region can disagree in pixels, throwing off click coordinates derived
    from OCR results here. If clicks land offset from where OCR found
    text, that's the likely cause."""
    def _do() -> Path:
        import mss
        import mss.tools

        CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
        path = CAPTURE_DIR / f"capture_{datetime.now():%Y%m%d_%H%M%S}.png"
        region = {
            "left": left,
            "top": top,
            "width": max(1, right - left),
            "height": max(1, bottom - top),
        }
        with mss.mss() as sct:
            shot = sct.grab(region)
            mss.tools.to_png(shot.rgb, shot.size, output=str(path))
        return path

    return await asyncio.to_thread(_do)


async def capture_active_window_region() -> Path | None:
    """Captures just the active window's region instead of the full
    screen. Returns None (not an error) if the active window's bounds
    can't be determined, so callers can cleanly fall back to
    capture_screen() — this is an optimization, not something that
    should ever block a read_screen request on its own failure."""
    def _do() -> Path | None:
        import mss
        from pywinauto import Desktop

        t0 = time.monotonic()
        try:
            desktop = Desktop(backend="uia")
            win = desktop.get_active()
            if win is None:
                return None
            rect = win.rectangle()
        except Exception as exc:
            log.info("[screen] Could not get active window rectangle (%s), will fall back to full screen.", exc)
            return None

        width, height = rect.width(), rect.height()
        if width < MIN_REGION_DIMENSION or height < MIN_REGION_DIMENSION:
            log.info("[screen] Active window rectangle looks invalid (%dx%d), falling back to full screen.", width, height)
            return None

        CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
        path = CAPTURE_DIR / f"capture_region_{datetime.now():%Y%m%d_%H%M%S}.png"
        region = {"left": rect.left, "top": rect.top, "width": width, "height": height}
        try:
            with mss.mss() as sct:
                sct_img = sct.grab(region)
                mss.tools.to_png(sct_img.rgb, sct_img.size, output=str(path))
        except Exception as exc:
            log.info("[screen] Region capture failed (%s), will fall back to full screen.", exc)
            return None

        log.info(
            "[screen] active-window-region capture took %.0fms -> %s (%dx%d)",
            (time.monotonic() - t0) * 1000, path.name, width, height,
        )
        return path

    return await asyncio.to_thread(_do)
