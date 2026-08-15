"""
Tests keyboard.py's validation logic directly (the VALID_KEYS allowlist,
hotkey length checks) plus the async flow with pyautogui mocked out —
pyautogui isn't functional in this sandbox (no display), so these prove
the tool's own logic is correct without needing a real keyboard.
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from core.errors import JarvisError
from tools import keyboard


def test_validate_key_accepts_known_key():
    assert keyboard._validate_key("Enter") == "enter"
    assert keyboard._validate_key("A") == "a"


def test_validate_key_rejects_unknown_key():
    with pytest.raises(JarvisError):
        keyboard._validate_key("banana")


@pytest.mark.asyncio
async def test_type_text_calls_pyautogui():
    fake_pyautogui = MagicMock()
    with patch.dict("sys.modules", {"pyautogui": fake_pyautogui}):
        result = await keyboard.type_text("hello world")
    fake_pyautogui.typewrite.assert_called_once_with("hello world", interval=0.02)
    assert "Typed" in result


@pytest.mark.asyncio
async def test_press_key_rejects_invalid_key_before_calling_pyautogui():
    fake_pyautogui = MagicMock()
    with patch.dict("sys.modules", {"pyautogui": fake_pyautogui}):
        with pytest.raises(JarvisError):
            await keyboard.press_key("qwerty123notakey")
    fake_pyautogui.press.assert_not_called()


@pytest.mark.asyncio
async def test_press_key_valid_calls_pyautogui():
    fake_pyautogui = MagicMock()
    with patch.dict("sys.modules", {"pyautogui": fake_pyautogui}):
        result = await keyboard.press_key("enter")
    fake_pyautogui.press.assert_called_once_with("enter")
    assert "Pressed" in result


@pytest.mark.asyncio
async def test_hotkey_valid_combo():
    fake_pyautogui = MagicMock()
    with patch.dict("sys.modules", {"pyautogui": fake_pyautogui}):
        result = await keyboard.hotkey(["ctrl", "s"])
    fake_pyautogui.hotkey.assert_called_once_with("ctrl", "s")
    assert "ctrl+s" in result


@pytest.mark.asyncio
async def test_hotkey_rejects_too_many_keys():
    with pytest.raises(JarvisError):
        await keyboard.hotkey(["ctrl", "alt", "shift", "win", "a"])


@pytest.mark.asyncio
async def test_hotkey_rejects_empty():
    with pytest.raises(JarvisError):
        await keyboard.hotkey([])


@pytest.mark.asyncio
async def test_hotkey_rejects_invalid_key_in_combo():
    with pytest.raises(JarvisError):
        await keyboard.hotkey(["ctrl", "notarealkey"])
