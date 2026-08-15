"""
Tests mouse.py's coordinate validation and click_control's UIA element
search logic, with pyautogui/pywinauto mocked out.
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from core.errors import JarvisError
from tools import mouse


@pytest.mark.asyncio
async def test_move_mouse_valid_coordinates():
    fake_pyautogui = MagicMock()
    with patch.dict("sys.modules", {"pyautogui": fake_pyautogui}):
        result = await mouse.move_mouse(100, 200)
    fake_pyautogui.moveTo.assert_called_once_with(100, 200, duration=0.1)
    assert "100" in result and "200" in result


@pytest.mark.asyncio
async def test_move_mouse_rejects_negative_coordinates():
    with pytest.raises(JarvisError):
        await mouse.move_mouse(-5, 100)


@pytest.mark.asyncio
async def test_move_mouse_rejects_absurd_coordinates():
    with pytest.raises(JarvisError):
        await mouse.move_mouse(999999, 100)


@pytest.mark.asyncio
async def test_click_at_coordinates():
    fake_pyautogui = MagicMock()
    with patch.dict("sys.modules", {"pyautogui": fake_pyautogui}):
        result = await mouse.click(x=50, y=60)
    fake_pyautogui.click.assert_called_once_with(50, 60, button="left")
    assert result == "Clicked."


@pytest.mark.asyncio
async def test_click_without_coordinates_clicks_current_position():
    fake_pyautogui = MagicMock()
    with patch.dict("sys.modules", {"pyautogui": fake_pyautogui}):
        await mouse.click()
    fake_pyautogui.click.assert_called_once_with(button="left")


@pytest.mark.asyncio
async def test_click_rejects_invalid_button():
    with pytest.raises(JarvisError):
        await mouse.click(x=1, y=1, button="banana")


def _fake_control(text, clickable=True):
    ctrl = MagicMock()
    ctrl.window_text.return_value = text
    return ctrl


def _fake_window(title, controls):
    win = MagicMock()
    win.window_text.return_value = title
    win.descendants.return_value = controls
    return win


@pytest.mark.asyncio
async def test_click_control_finds_and_clicks_matching_element():
    save_btn = _fake_control("Save")
    cancel_btn = _fake_control("Cancel")
    window = _fake_window("Notepad", [save_btn, cancel_btn])

    fake_desktop_instance = MagicMock()
    fake_desktop_instance.windows.return_value = [window]
    fake_desktop_cls = MagicMock(return_value=fake_desktop_instance)
    fake_pywinauto = MagicMock()
    fake_pywinauto.Desktop = fake_desktop_cls

    with patch.dict("sys.modules", {"pywinauto": fake_pywinauto}):
        result = await mouse.click_control("Notepad", "Save")

    save_btn.click_input.assert_called_once()
    cancel_btn.click_input.assert_not_called()
    assert "Save" in result


@pytest.mark.asyncio
async def test_click_control_raises_when_window_not_found():
    fake_desktop_instance = MagicMock()
    fake_desktop_instance.windows.return_value = []
    fake_pywinauto = MagicMock()
    fake_pywinauto.Desktop = MagicMock(return_value=fake_desktop_instance)

    with patch.dict("sys.modules", {"pywinauto": fake_pywinauto}):
        with pytest.raises(JarvisError):
            await mouse.click_control("NonexistentApp", "Save")


@pytest.mark.asyncio
async def test_click_control_raises_when_control_not_found():
    window = _fake_window("Notepad", [_fake_control("Cancel")])
    fake_desktop_instance = MagicMock()
    fake_desktop_instance.windows.return_value = [window]
    fake_pywinauto = MagicMock()
    fake_pywinauto.Desktop = MagicMock(return_value=fake_desktop_instance)

    with patch.dict("sys.modules", {"pywinauto": fake_pywinauto}):
        with pytest.raises(JarvisError):
            await mouse.click_control("Notepad", "SomeButtonThatDoesntExist")
