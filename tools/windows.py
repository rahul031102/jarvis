"""
"What's open, and let me switch to it / read it." Uses pywinauto's UIA
backend, filtered by control_type (faster and more accurate than scanning
every element — see tools/uia_helpers.py for why), with timeouts and a
retry for Chromium's lazy accessibility-tree activation.

Note on "browser tabs": Chrome's own tab STRIP is native UI (not web
content), so it IS reliably readable via UIA as TabItem elements — see
list_browser_tabs(). The web PAGE content inside a tab is a different
story: that's what triggers the lazy-tree/timeout handling in
uia_helpers.py, and reading it thoroughly is still best done with
read_screen (OCR) for anything read_window_text comes back empty on.
"""
from __future__ import annotations

import asyncio

from core.errors import JarvisError
from tools.uia_helpers import (
    CLICKABLE_CONTROL_TYPES,
    TEXT_CONTROL_TYPES,
    find_window_sync,
    get_desktop,
    get_descendants_by_types,
    run_uia,
    with_retry_if_empty,
)


async def list_open_windows() -> str:
    def _do() -> list[str]:
        desktop = get_desktop()
        windows = []
        for w in desktop.windows():
            try:
                title = w.window_text().strip()
                if title:
                     windows.append(title)
            except Exception:
                continue
        return windows

    result = await run_uia(_do)
    if not result:
        return "I don't see any open windows right now."
    return "; ".join(result[:30])


async def get_active_window() -> str:
    def _do() -> str | None:
        desktop = get_desktop()
        try:
            win = desktop.get_active()
        except Exception:
            return None
        if win is None:
            return None
        return win.window_text().strip() or "(untitled window)"

    result = await run_uia(_do)
    if result is None:
        raise JarvisError("I can't tell what window is currently active.")
    return result


async def focus_window(name: str) -> str:
    """Bring a window to the foreground by fuzzy title match, so a
    following type_text/click/hotkey call reliably lands in the right app."""
    def _do() -> str | None:
        win = find_window_sync(name)
        if win is None:
            return None
        win.set_focus()
        return win.window_text().strip()

    result = await run_uia(_do)
    if result is None:
        raise JarvisError(f"I couldn't find a window matching '{name}'.")
    return f"Switched to {result}."


async def read_window_text(name: str) -> str:
    """Reads a window's text content via the UIA accessibility tree,
    restricted to actual content control types (Text, Edit, Document,
    Hyperlink, ListItem) rather than every element. Walks the tree ONCE
    and filters by type in Python — not once per type — which is what
    keeps this usable on Chrome/WhatsApp/Electron apps instead of taking
    tens of seconds. One retry-after-delay handles Chromium's lazy tree
    activation. If nothing comes back, that means the content genuinely
    isn't exposed this way (e.g. a canvas/video) — read_screen (OCR) is
    the fallback for that case, not a bug here."""
    def _do() -> list[str] | None:
        win = find_window_sync(name)
        if win is None:
            return None
        texts: list[str] = []
        for ctrl in get_descendants_by_types(win, TEXT_CONTROL_TYPES, depth=6):
            try:
                text = ctrl.window_text().strip()
                if text and text not in texts:
                    texts.append(text)
            except Exception:
                continue
        return texts

    result = await with_retry_if_empty(_do, is_empty=lambda r: not r)

    if result is None:
        raise JarvisError(f"I couldn't find a window matching '{name}'.")
    if not result:
        raise JarvisError(
            "That window doesn't expose readable text through accessibility — "
            "try 'read the screen' instead, which reads it visually."
        )
    return "; ".join(result[:80])


async def list_browser_tabs(app_name: str) -> str:
    """Lists a browser's open tabs by reading its native tab strip (UIA
    TabItem elements) — this works even though reading the web PAGE
    content inside a tab is unreliable, because the tab strip itself is
    the browser's own native UI, not rendered web content."""
    def _do() -> list[str] | None:
        win = find_window_sync(app_name)
        if win is None:
            return None
        tabs = []
        for ctrl in get_descendants_by_types(win, ("TabItem",)):
            try:
                text = ctrl.window_text().strip()
                if text and text not in tabs:
                    tabs.append(text)
            except Exception:
                continue
        return tabs

    result = await with_retry_if_empty(_do, is_empty=lambda r: not r)

    if result is None:
        raise JarvisError(f"I couldn't find a window matching '{app_name}'.")
    if not result:
        raise JarvisError(
            f"I couldn't read {app_name}'s tabs — it may not expose a standard tab strip."
        )
    return "; ".join(result[:30])
