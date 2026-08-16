"""
URL opening, web search, browser tab controls, and music/video playback macros.
Uses default browser via webbrowser and simulates keystrokes for tab navigation.
"""
from __future__ import annotations

import asyncio
import re
import webbrowser
from urllib.parse import quote_plus

from core.errors import JarvisError
from tools import keyboard, windows


async def open_url(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        await asyncio.to_thread(webbrowser.open, url)
    except Exception as exc:
        raise JarvisError("I couldn't open that page.", technical_detail=str(exc))
    return f"Opening {url}."


async def web_search(query: str) -> str:
    search_url = f"https://www.google.com/search?q={quote_plus(query)}"
    try:
        await asyncio.to_thread(webbrowser.open, search_url)
    except Exception as exc:
        raise JarvisError("I couldn't run that search.", technical_detail=str(exc))
    return f"Searching for {query}."


async def open_website_or_search(query: str) -> str:
    domain_pattern = re.compile(r"^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,6}(/.*)?$")
    if query.startswith(("http://", "https://")) or domain_pattern.match(query):
        return await open_url(query)
    return await web_search(query)


BROWSER_NAMES = ["Chrome", "Edge", "Firefox", "Opera", "Browser"]


async def _ensure_browser_focused() -> str:
    """Make sure a browser window actually has focus before sending
    tab-control hotkeys (Ctrl+W/Ctrl+T/etc). Without this, if some other
    app happens to be focused when the user says 'close this tab', the
    hotkey fires at whatever's focused instead — e.g. Ctrl+W closing a
    document in Word. Mirrors the check focus_tab already did."""
    active_win = await windows.get_active_window()
    for b in BROWSER_NAMES:
        if b.lower() in active_win.lower():
            return b

    for b in BROWSER_NAMES:
        try:
            await windows.focus_window(b)
            return b
        except Exception:
            continue

    raise JarvisError("I couldn't find an active browser window.")


async def control_browser_tabs(action: str, tab_name: str | None = None) -> str:
    if action == "new_tab":
        await _ensure_browser_focused()
        await keyboard.hotkey(["ctrl", "t"])
        return "Opened a new tab."
    elif action == "close_tab":
        await _ensure_browser_focused()
        await keyboard.hotkey(["ctrl", "w"])
        return "Closed the current tab."
    elif action == "next_tab":
        await _ensure_browser_focused()
        await keyboard.hotkey(["ctrl", "pagedown"])
        return "Switched to the next tab."
    elif action == "prev_tab":
        await _ensure_browser_focused()
        await keyboard.hotkey(["ctrl", "pageup"])
        return "Switched to the previous tab."
    elif action == "focus_tab":
        if not tab_name:
            raise JarvisError("Please specify a tab name to focus.")

        matched_browser = await _ensure_browser_focused()

        tab_list_str = await windows.list_browser_tabs(matched_browser)
        tab_list = [t.strip() for t in tab_list_str.split(";")]
        
        needle = tab_name.strip().lower()
        target_idx = -1
        for idx, t in enumerate(tab_list):
            if needle in t.lower():
                target_idx = idx
                break
        
        if target_idx == -1:
            raise JarvisError(f"I couldn't find a tab matching '{tab_name}'.")
        
        if target_idx < 8:
            await keyboard.hotkey(["ctrl", str(target_idx + 1)])
        else:
            await keyboard.hotkey(["ctrl", "9"])
        return f"Focused tab '{tab_list[target_idx]}'."
    else:
        raise JarvisError(f"Unknown browser tab action: {action}")


async def play_music(query: str) -> str:
    # webbrowser.open() returns True/False and basically never raises even
    # when there's no handler for a custom "spotify:" URI scheme — it just
    # silently does nothing. The old try/except around it was dead code:
    # nothing there ever threw, so we'd always claim success on Spotify even
    # when Spotify isn't installed. Check the actual return value instead,
    # and give the OS launch a moment to actually take effect before
    # deciding whether to fall back.
    spotify_url = f"spotify:search:{quote_plus(query)}"
    launched = await asyncio.to_thread(webbrowser.open, spotify_url)
    if launched:
        await asyncio.sleep(0.8)
        # Even a "successful" launch call can't confirm Spotify actually
        # opened (no handler still returns True on some platforms), so we
        # additionally check whether a Spotify window shows up.
        try:
            await windows.focus_window("Spotify")
            return f"Searching and playing '{query}' on Spotify."
        except Exception:
            pass

    yt_url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
    await asyncio.to_thread(webbrowser.open, yt_url)
    return f"Spotify doesn't seem to be available, so I searched '{query}' on YouTube instead."
