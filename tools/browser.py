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


async def control_browser_tabs(action: str, tab_name: str | None = None) -> str:
    if action == "new_tab":
        await keyboard.hotkey(["ctrl", "t"])
        return "Opened a new tab."
    elif action == "close_tab":
        await keyboard.hotkey(["ctrl", "w"])
        return "Closed the current tab."
    elif action == "next_tab":
        await keyboard.hotkey(["ctrl", "pagedown"])
        return "Switched to the next tab."
    elif action == "prev_tab":
        await keyboard.hotkey(["ctrl", "pageup"])
        return "Switched to the previous tab."
    elif action == "focus_tab":
        if not tab_name:
            raise JarvisError("Please specify a tab name to focus.")
        
        browser_names = ["Chrome", "Edge", "Firefox", "Opera", "Browser"]
        active_win = await windows.get_active_window()
        matched_browser = None
        for b in browser_names:
            if b.lower() in active_win.lower():
                matched_browser = b
                break
        
        if not matched_browser:
            for b in browser_names:
                try:
                    await windows.focus_window(b)
                    matched_browser = b
                    break
                except Exception:
                    continue
        
        if not matched_browser:
            raise JarvisError("I couldn't find an active browser window.")
        
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
    spotify_url = f"spotify:search:{quote_plus(query)}"
    try:
        await asyncio.to_thread(webbrowser.open, spotify_url)
        return f"Searching and playing '{query}' on Spotify."
    except Exception:
        yt_url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
        await asyncio.to_thread(webbrowser.open, yt_url)
        return f"Searching and playing '{query}' on YouTube."
