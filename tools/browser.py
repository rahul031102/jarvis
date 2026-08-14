"""
URL opening and web search. Uses the OS default browser via `webbrowser`
for simple open/search actions (fast, no automation overhead). Playwright
is reserved for tasks that need to actually read page content — see
tools/browser_automation.py (added in the browser-control milestone).
"""
from __future__ import annotations

import asyncio
import webbrowser
from urllib.parse import quote_plus

from core.errors import JarvisError


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
