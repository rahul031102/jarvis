"""
Keyboard control. Uses pyautogui — global, simple key-name mapping (the
LLM naturally produces strings like "enter", "ctrl", "s", which map
directly onto pyautogui's key names, unlike pywinauto's own {CURLY_BRACE}
syntax which would need extra translation).

These act on whatever currently has focus — call focus_window() first if
you need to target a specific app rather than whatever the user last
clicked.
"""
from __future__ import annotations

import asyncio

from core.errors import JarvisError

# A conservative allowlist of key names pyautogui understands, so a
# malformed/hallucinated key name fails clearly instead of silently doing
# nothing or (worse) pyautogui interpreting it unpredictably.
VALID_KEYS = {
    "enter", "return", "tab", "esc", "escape", "space", "backspace", "delete",
    "up", "down", "left", "right", "home", "end", "pageup", "pagedown",
    "ctrl", "alt", "shift", "win", "capslock",
    "f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8", "f9", "f10", "f11", "f12",
} | set("abcdefghijklmnopqrstuvwxyz0123456789")


def _validate_key(key: str) -> str:
    normalized = key.strip().lower()
    if normalized not in VALID_KEYS:
        raise JarvisError(f"'{key}' isn't a key I recognize.")
    return normalized


async def type_text(text: str) -> str:
    def _do() -> None:
        import pyautogui

        pyautogui.typewrite(text, interval=0.02)

    await asyncio.to_thread(_do)
    return "Typed it."


async def press_key(key: str) -> str:
    validated = _validate_key(key)

    def _do() -> None:
        import pyautogui

        pyautogui.press(validated)

    await asyncio.to_thread(_do)
    return f"Pressed {key}."


async def hotkey(keys: list[str]) -> str:
    if not keys or len(keys) > 4:
        raise JarvisError("That doesn't look like a valid key combination.")
    validated = [_validate_key(k) for k in keys]

    def _do() -> None:
        import pyautogui

        pyautogui.hotkey(*validated)

    await asyncio.to_thread(_do)
    return f"Pressed {'+'.join(keys)}."
