"""
Tests windows.py's window enumeration, focus, and text-reading logic with
pywinauto mocked out.
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from core.errors import JarvisError
from tools import windows


def _fake_window(title):
    w = MagicMock()
    w.window_text.return_value = title
    return w


def _patch_desktop(fake_windows, active=None):
    fake_desktop_instance = MagicMock()
    fake_desktop_instance.windows.return_value = fake_windows
    fake_desktop_instance.get_active.return_value = active
    fake_pywinauto = MagicMock()
    fake_pywinauto.Desktop = MagicMock(return_value=fake_desktop_instance)
    return fake_pywinauto


@pytest.mark.asyncio
async def test_list_open_windows_returns_titles():
    fake_windows = [_fake_window("Notepad"), _fake_window("Google Chrome"), _fake_window("")]
    fake_pywinauto = _patch_desktop(fake_windows)

    with patch.dict("sys.modules", {"pywinauto": fake_pywinauto}):
        result = await windows.list_open_windows()

    assert "Notepad" in result
    assert "Google Chrome" in result


@pytest.mark.asyncio
async def test_list_open_windows_empty_case():
    fake_pywinauto = _patch_desktop([])
    with patch.dict("sys.modules", {"pywinauto": fake_pywinauto}):
        result = await windows.list_open_windows()
    assert "don't see" in result.lower()


@pytest.mark.asyncio
async def test_get_active_window_returns_title():
    active = _fake_window("VS Code")
    fake_pywinauto = _patch_desktop([], active=active)
    with patch.dict("sys.modules", {"pywinauto": fake_pywinauto}):
        result = await windows.get_active_window()
    assert result == "VS Code"


@pytest.mark.asyncio
async def test_focus_window_finds_fuzzy_match_and_calls_set_focus():
    notepad = _fake_window("Untitled - Notepad")
    fake_pywinauto = _patch_desktop([notepad])
    with patch.dict("sys.modules", {"pywinauto": fake_pywinauto}):
        result = await windows.focus_window("notepad")
    notepad.set_focus.assert_called_once()
    assert "Notepad" in result


@pytest.mark.asyncio
async def test_focus_window_raises_when_not_found():
    fake_pywinauto = _patch_desktop([_fake_window("Calculator")])
    with patch.dict("sys.modules", {"pywinauto": fake_pywinauto}):
        with pytest.raises(JarvisError):
            await windows.focus_window("nonexistent app")


@pytest.mark.asyncio
async def test_read_window_text_collects_descendant_text():
    window = _fake_window("My Editor")
    window.descendants.return_value = [_fake_window("Line 1 content"), _fake_window("Line 2 content")]
    fake_pywinauto = _patch_desktop([window])
    with patch.dict("sys.modules", {"pywinauto": fake_pywinauto}):
        result = await windows.read_window_text("editor")
    assert "Line 1 content" in result
    assert "Line 2 content" in result


@pytest.mark.asyncio
async def test_read_window_text_raises_when_no_text_found():
    window = _fake_window("Blank Window")
    window.descendants.return_value = []
    fake_pywinauto = _patch_desktop([window])
    with patch.dict("sys.modules", {"pywinauto": fake_pywinauto}):
        with pytest.raises(JarvisError):
            await windows.read_window_text("blank")


@pytest.mark.asyncio
async def test_read_window_text_raises_when_window_not_found():
    fake_pywinauto = _patch_desktop([])
    with patch.dict("sys.modules", {"pywinauto": fake_pywinauto}):
        with pytest.raises(JarvisError):
            await windows.read_window_text("nothing")


@pytest.mark.asyncio
async def test_read_window_text_filters_by_control_type():
    """Proves read_window_text queries specific control types (Text, Edit,
    Document, Hyperlink, ListItem) rather than scanning every element —
    the performance/reliability fix for Chromium apps."""
    window = _fake_window("My Editor")
    seen_control_types = []

    def fake_descendants(control_type=None):
        seen_control_types.append(control_type)
        if control_type == "Text":
            return [_fake_window("Some paragraph text")]
        return []

    window.descendants = MagicMock(side_effect=fake_descendants)
    fake_pywinauto = _patch_desktop([window])

    with patch.dict("sys.modules", {"pywinauto": fake_pywinauto}):
        result = await windows.read_window_text("editor")

    assert "Some paragraph text" in result
    from tools.uia_helpers import TEXT_CONTROL_TYPES
    assert set(seen_control_types) == set(TEXT_CONTROL_TYPES)


@pytest.mark.asyncio
async def test_list_browser_tabs_reads_tabitem_elements():
    window = _fake_window("Google Chrome")
    tab1, tab2 = _fake_window("GitHub"), _fake_window("Gmail")
    window.descendants = MagicMock(return_value=[tab1, tab2])
    fake_pywinauto = _patch_desktop([window])

    with patch.dict("sys.modules", {"pywinauto": fake_pywinauto}):
        result = await windows.list_browser_tabs("chrome")

    assert "GitHub" in result
    assert "Gmail" in result
    window.descendants.assert_called_with(control_type="TabItem")


@pytest.mark.asyncio
async def test_list_browser_tabs_raises_when_window_not_found():
    fake_pywinauto = _patch_desktop([])
    with patch.dict("sys.modules", {"pywinauto": fake_pywinauto}):
        with pytest.raises(JarvisError):
            await windows.list_browser_tabs("nonexistent browser")


@pytest.mark.asyncio
async def test_list_browser_tabs_raises_when_no_tabs_found():
    window = _fake_window("Notepad")  # not a browser, no TabItem elements
    window.descendants = MagicMock(return_value=[])
    fake_pywinauto = _patch_desktop([window])

    with patch.dict("sys.modules", {"pywinauto": fake_pywinauto}):
        with pytest.raises(JarvisError):
            await windows.list_browser_tabs("notepad")
