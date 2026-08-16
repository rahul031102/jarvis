"""
Shared helpers for UIA-based window interaction, used by both
tools/windows.py and tools/mouse.py.

Two real problems this exists to solve, both documented in pywinauto's own
issue tracker (not theoretical):

1. Chromium-based apps (Chrome, Edge, WhatsApp Desktop, Slack, Discord,
   etc.) build their accessibility tree LAZILY — it's mostly empty until
   something like a screen reader or a UIA client "wakes it up" by
   querying it. That means the first read/click attempt right after
   opening one of these apps can come back empty even though the content
   is genuinely there a moment later. We handle this with one bounded
   retry after a short delay, not by giving up immediately.

2. descendants() on a big Chromium tree has been reported to take 17+
   seconds in bad cases (pywinauto issue #842). An unbounded call here
   would make JARVIS appear to hang. Every UIA call in this module goes
   through a hard timeout so a slow app degrades to a clear spoken error
   instead of silence.
"""
from __future__ import annotations

import asyncio

from core.errors import JarvisError

UIA_TIMEOUT_S = 8.0
RETRY_DELAY_S = 0.4

# UIA control types worth reading as "content" — deliberately excludes
# generic containers (Pane, Group, Window) which just add noise.
TEXT_CONTROL_TYPES = ("Text", "Edit", "Document", "Hyperlink", "ListItem")

# UIA control types worth searching when looking for something to click.
CLICKABLE_CONTROL_TYPES = (
    "Button", "Hyperlink", "MenuItem", "TabItem", "CheckBox", "RadioButton", "ListItem",
)


def get_desktop():
    from pywinauto import Desktop

    return Desktop(backend="uia")


def find_window_sync(needle: str):
    """Blocking. Must be called from inside a thread (asyncio.to_thread)."""
    desktop = get_desktop()
    needle = needle.strip().lower()
    for w in desktop.windows():
        try:
            if needle in w.window_text().strip().lower():
                return w
        except Exception:
            continue
    return None


def get_descendants_by_types(win, wanted_types: tuple[str, ...], depth: int | None = None) -> list:
    """Walk the accessibility tree ONCE and filter by type in Python,
    instead of calling descendants(control_type=X) separately per type.

    This matters a lot in practice: calling descendants() N times for N
    control types means N full UIA tree-walks. On a slow app (WhatsApp
    Desktop, Chrome) each walk can itself take a couple of seconds — doing
    7 of them sequentially (once per type in CLICKABLE_CONTROL_TYPES) for
    every click, times 2 if it retries, is exactly what turned a single
    "click Send" into a 40-60 second wait. One walk, filtered afterward,
    fixes that at the source.
    """
    wanted = set(wanted_types)
    matches = []
    try:
        all_ctrls = win.descendants(depth=depth) if depth is not None else win.descendants()
    except Exception:
        return matches
    for ctrl in all_ctrls:
        try:
            if ctrl.friendly_class_name() in wanted:
                matches.append(ctrl)
        except Exception:
            continue
    return matches


async def find_window(needle: str, *, app_label: str):
    win = await asyncio.wait_for(asyncio.to_thread(find_window_sync, needle), timeout=UIA_TIMEOUT_S)
    if win is None:
        raise JarvisError(f"I couldn't find a window matching '{app_label}'.")
    return win


async def run_uia(func, *args, timeout: float = UIA_TIMEOUT_S):
    """Run a blocking pywinauto call in a thread with a hard timeout, so a
    slow/hung accessibility tree becomes a clear error instead of a freeze."""
    try:
        return await asyncio.wait_for(asyncio.to_thread(func, *args), timeout=timeout)
    except asyncio.TimeoutError:
        raise JarvisError(
            "That app is taking too long to respond to accessibility queries — "
            "it may still be loading, or doesn't expose its content this way."
        )


async def with_retry_if_empty(func, *args, is_empty):
    """Runs func once; if the result looks empty (per is_empty), waits
    briefly and tries once more. Exists specifically for Chromium's lazy
    accessibility-tree activation — the content is often there a moment
    after the first query, not never."""
    result = await run_uia(func, *args)
    if is_empty(result):
        await asyncio.sleep(RETRY_DELAY_S)
        result = await run_uia(func, *args)
    return result
