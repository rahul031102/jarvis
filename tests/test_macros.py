"""
Tests for all the A to Z high-level desktop macro tools.
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from core.errors import JarvisError
from tools import browser, filesystem, system


# --- Filesystem Macros ---

@pytest.mark.asyncio
async def test_quick_note():
    mock_open = MagicMock()
    with patch("builtins.open", mock_open):
        result = await filesystem.quick_note("hello note")
    assert "notes.txt" in result
    mock_open.assert_called_once()


@pytest.mark.asyncio
async def test_create_file():
    mock_mkdir = MagicMock()
    mock_write = MagicMock()
    with patch.object(Path, "mkdir", mock_mkdir), patch.object(Path, "write_text", mock_write):
        result = await filesystem.create_file("C:/some/file.txt", "content here")
    assert "file.txt" in result
    mock_mkdir.assert_called_once()
    mock_write.assert_called_once_with("content here", encoding="utf-8")


@pytest.mark.asyncio
async def test_open_system_folder():
    mock_start = MagicMock()
    with patch("os.startfile", mock_start):
        result = await filesystem.open_system_folder("desktop")
    assert "desktop" in result.lower()
    mock_start.assert_called_once()


@pytest.mark.asyncio
async def test_find_and_open_file():
    mock_start = MagicMock()
    # Mocking rglob to return a file
    mock_file = MagicMock(spec=Path)
    mock_file.is_file.return_value = True
    mock_file.name = "matching_doc.pdf"
    
    with patch("os.startfile", mock_start), patch.object(Path, "exists", return_value=True), patch.object(Path, "rglob", return_value=[mock_file]):
        result = await filesystem.find_and_open_file("matching_doc")
    assert "matching_doc.pdf" in result
    mock_start.assert_called_once()


# --- Browser Macros ---

@pytest.mark.asyncio
async def test_open_website_or_search_url():
    mock_open = MagicMock()
    with patch("webbrowser.open", mock_open):
        result = await browser.open_website_or_search("github.com")
    assert "github.com" in result
    mock_open.assert_called_once_with("https://github.com")


@pytest.mark.asyncio
async def test_open_website_or_search_query():
    mock_open = MagicMock()
    with patch("webbrowser.open", mock_open):
        result = await browser.open_website_or_search("how to bake bread")
    assert "Searching for" in result
    mock_open.assert_called_once()
    assert "google.com/search?q=" in mock_open.call_args[0][0]


@pytest.mark.asyncio
async def test_control_browser_tabs_basic():
    mock_hotkey = MagicMock()
    with patch("tools.keyboard.hotkey", mock_hotkey):
        res1 = await browser.control_browser_tabs("new_tab")
        res2 = await browser.control_browser_tabs("close_tab")
    assert "new" in res1
    assert "Closed" in res2
    mock_hotkey.assert_any_call(["ctrl", "t"])
    mock_hotkey.assert_any_call(["ctrl", "w"])


@pytest.mark.asyncio
async def test_play_music():
    mock_open = MagicMock()
    with patch("webbrowser.open", mock_open):
        result = await browser.play_music("classical piano")
    assert "classical piano" in result
    mock_open.assert_called_once()


# --- System & Window Macros ---

@pytest.mark.asyncio
async def test_media_control():
    mock_press = MagicMock()
    with patch("pyautogui.press", mock_press):
        result = await system.media_control("play_pause")
    assert "play_pause" in result
    mock_press.assert_called_once_with("playpause")


@pytest.mark.asyncio
async def test_window_action():
    mock_hotkey = MagicMock()
    with patch("pyautogui.hotkey", mock_hotkey):
        result = await system.window_action("maximize")
    assert "maximize" in result
    mock_hotkey.assert_called_once_with("win", "up")


@pytest.mark.asyncio
async def test_get_system_status():
    mock_cpu = MagicMock(return_value=12.5)
    mock_virtual = MagicMock()
    mock_virtual.percent = 45.0
    mock_disk = MagicMock()
    mock_disk.percent = 60.0
    
    with patch("psutil.cpu_percent", mock_cpu), \
         patch("psutil.virtual_memory", return_value=mock_virtual), \
         patch("psutil.disk_usage", return_value=mock_disk), \
         patch("psutil.sensors_battery", return_value=None):
        result = await system.get_system_status()
    
    assert "CPU: 12.5%" in result
    assert "RAM: 45.0%" in result
    assert "Disk: 60.0%" in result


@pytest.mark.asyncio
async def test_calculate():
    res = await system.calculate("2 + 2 * 3")
    assert res == "Result: 8"

    with pytest.raises(JarvisError):
        await system.calculate("import os")


@pytest.mark.asyncio
async def test_forward_whatsapp_media():
    from tools import whatsapp
    mock_focus = MagicMock()
    mock_hotkey = MagicMock()
    mock_type = MagicMock()
    mock_press = MagicMock()

    with patch("tools.windows.focus_window", mock_focus), \
         patch("tools.keyboard.hotkey", mock_hotkey), \
         patch("tools.keyboard.type_text", mock_type), \
         patch("tools.keyboard.press_key", mock_press):
        result = await whatsapp.forward_whatsapp_media("Govardhan", "Mummy")

    assert "forwarded" in result.lower()
    mock_focus.assert_called_once_with("WhatsApp")
    mock_hotkey.assert_any_call(["ctrl", "c"])
    mock_hotkey.assert_any_call(["ctrl", "v"])
    mock_type.assert_any_call("Govardhan")
    mock_type.assert_any_call("Mummy")
