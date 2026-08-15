"""
Mouse control. Two ways to click, both real:

1. click(x, y) — raw screen coordinates via pyautogui. Simple, universal,
   but fragile (breaks if the window moves/resizes) — the spec's own
   stated fallback.

2. click_control(app_name, control_text) — finds a named button/control
   inside a specific window via pywinauto's UIA tree and clicks it
   directly, no coordinates involved. This is what the spec means by
   "prefer DOM/accessibility-based interaction over fragile screen
   coordinates whenever possible" — use this whenever the user names what
   they want clicked ("click Save", "click the Cancel button") rather than
   giving you a screen position.
"""
from __future__ import annotations

import asyncio

from core.errors import JarvisError

# Reasonable screen bounds sanity check — catches obviously-bad
# LLM-hallucinated coordinates before they're sent to pyautogui.
MAX_COORDINATE = 10000


async def move_mouse(x: int, y: int) -> str:
    if not (0 <= x <= MAX_COORDINATE and 0 <= y <= MAX_COORDINATE):
        raise JarvisError("Those coordinates don't look valid.")

    def _do() -> None:
        import pyautogui

        pyautogui.moveTo(x, y, duration=0.1)

    await asyncio.to_thread(_do)
    return f"Moved to ({x}, {y})."


async def click(x: int | None = None, y: int | None = None, button: str = "left") -> str:
    if button not in ("left", "right", "middle"):
        raise JarvisError(f"'{button}' isn't a valid mouse button.")
    if x is not None and y is not None:
        if not (0 <= x <= MAX_COORDINATE and 0 <= y <= MAX_COORDINATE):
            raise JarvisError("Those coordinates don't look valid.")

    def _do() -> None:
        import pyautogui

        if x is not None and y is not None:
            pyautogui.click(x, y, button=button)
        else:
            pyautogui.click(button=button)

    await asyncio.to_thread(_do)
    return "Clicked."


async def click_control(app_name: str, control_text: str) -> str:
    """Finds a clickable control (button, link, tab, checkbox, etc.) by
    its visible text and clicks it directly — no coordinates involved.
    Walks the accessibility tree ONCE and filters by type in Python
    afterward, rather than calling descendants() separately per control
    type — the latter turns one click into 7+ full tree-walks, which is
    what made WhatsApp/Chrome clicks take tens of seconds. One
    retry-after-delay handles Chromium apps whose accessibility tree
    activates lazily on first query — but only retries when the window
    was found and the control search came up empty, not when the window
    itself doesn't exist."""
    from tools.uia_helpers import CLICKABLE_CONTROL_TYPES, find_window_sync, get_descendants_by_types, run_uia, RETRY_DELAY_S

    def _search() -> tuple[bool, bool]:
        """Returns (window_found, control_found)."""
        win = find_window_sync(app_name)
        if win is None:
            return (False, False)
        needle_ctrl = control_text.strip().lower()
        for ctrl in get_descendants_by_types(win, CLICKABLE_CONTROL_TYPES):
            try:
                text = ctrl.window_text().strip().lower()
                if needle_ctrl in text:
                    ctrl.click_input()
                    return (True, True)
            except Exception:
                continue
        return (True, False)

    window_found, control_found = await run_uia(_search)

    if not window_found:
        raise JarvisError(f"I couldn't find a window matching '{app_name}'.")

    if not control_found:
        # Retry once — the window exists but nothing matched, which is
        # exactly the lazy-accessibility-tree case for Chromium apps.
        await asyncio.sleep(RETRY_DELAY_S)
        window_found, control_found = await run_uia(_search)
        if not control_found:
            raise JarvisError(f"I couldn't find '{control_text}' in {app_name}.")

    return f"Clicked '{control_text}' in {app_name}."
