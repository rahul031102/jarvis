"""
Tests vision/screen.py's capture_active_window_region — the fallback
logic (returns None rather than raising, so read_screen can cleanly fall
back to full-screen capture) and the sanity check on tiny/invalid rects.
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from vision import screen


def _fake_rect(left=100, top=100, width=700, height=500):
    rect = MagicMock()
    rect.left = left
    rect.top = top
    rect.width.return_value = width
    rect.height.return_value = height
    return rect


@pytest.mark.asyncio
async def test_capture_region_returns_none_when_no_active_window():
    fake_desktop = MagicMock()
    fake_desktop.get_active.return_value = None
    fake_pywinauto = MagicMock()
    fake_pywinauto.Desktop = MagicMock(return_value=fake_desktop)

    with patch.dict("sys.modules", {"pywinauto": fake_pywinauto}):
        result = await screen.capture_active_window_region()

    assert result is None


@pytest.mark.asyncio
async def test_capture_region_returns_none_when_rectangle_lookup_fails():
    fake_win = MagicMock()
    fake_win.rectangle.side_effect = Exception("UIA error")
    fake_desktop = MagicMock()
    fake_desktop.get_active.return_value = fake_win
    fake_pywinauto = MagicMock()
    fake_pywinauto.Desktop = MagicMock(return_value=fake_desktop)

    with patch.dict("sys.modules", {"pywinauto": fake_pywinauto}):
        result = await screen.capture_active_window_region()

    assert result is None


@pytest.mark.asyncio
async def test_capture_region_returns_none_for_suspiciously_tiny_rect():
    """A near-zero-size rectangle is almost certainly a bad/stale UIA
    read, not a real tiny dialog worth capturing — should fall back
    rather than try to OCR a 5x5 pixel image."""
    fake_win = MagicMock()
    fake_win.rectangle.return_value = _fake_rect(width=5, height=5)
    fake_desktop = MagicMock()
    fake_desktop.get_active.return_value = fake_win
    fake_pywinauto = MagicMock()
    fake_pywinauto.Desktop = MagicMock(return_value=fake_desktop)

    with patch.dict("sys.modules", {"pywinauto": fake_pywinauto}):
        result = await screen.capture_active_window_region()

    assert result is None


@pytest.mark.asyncio
async def test_capture_region_calls_mss_grab_with_correct_bounds(tmp_path):
    fake_win = MagicMock()
    fake_win.rectangle.return_value = _fake_rect(left=200, top=150, width=700, height=500)
    fake_desktop = MagicMock()
    fake_desktop.get_active.return_value = fake_win
    fake_pywinauto = MagicMock()
    fake_pywinauto.Desktop = MagicMock(return_value=fake_desktop)

    fake_sct_img = MagicMock()
    fake_sct_img.rgb = b""
    fake_sct_img.size = (700, 500)
    fake_sct_instance = MagicMock()
    fake_sct_instance.grab.return_value = fake_sct_img
    fake_sct_instance.__enter__ = MagicMock(return_value=fake_sct_instance)
    fake_sct_instance.__exit__ = MagicMock(return_value=False)
    fake_mss_module = MagicMock()
    fake_mss_module.mss.return_value = fake_sct_instance
    fake_mss_module.tools.to_png = MagicMock()

    with patch.dict("sys.modules", {"pywinauto": fake_pywinauto, "mss": fake_mss_module}), \
         patch.object(screen, "CAPTURE_DIR", tmp_path):
        result = await screen.capture_active_window_region()

    assert result is not None
    fake_sct_instance.grab.assert_called_once_with({"left": 200, "top": 150, "width": 700, "height": 500})


@pytest.mark.asyncio
async def test_capture_region_returns_none_when_mss_grab_fails(tmp_path):
    fake_win = MagicMock()
    fake_win.rectangle.return_value = _fake_rect()
    fake_desktop = MagicMock()
    fake_desktop.get_active.return_value = fake_win
    fake_pywinauto = MagicMock()
    fake_pywinauto.Desktop = MagicMock(return_value=fake_desktop)

    fake_sct_instance = MagicMock()
    fake_sct_instance.grab.side_effect = Exception("capture backend error")
    fake_sct_instance.__enter__ = MagicMock(return_value=fake_sct_instance)
    fake_sct_instance.__exit__ = MagicMock(return_value=False)
    fake_mss_module = MagicMock()
    fake_mss_module.mss.return_value = fake_sct_instance

    with patch.dict("sys.modules", {"pywinauto": fake_pywinauto, "mss": fake_mss_module}), \
         patch.object(screen, "CAPTURE_DIR", tmp_path):
        result = await screen.capture_active_window_region()

    assert result is None
