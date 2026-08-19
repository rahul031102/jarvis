"""
Tests the read_screen tool's logic: region-capture-first with full-screen
fallback, empty-result handling, and truncation — with the actual screen
capture and OCR calls mocked out (no real screenshot or Tesseract binary
needed to verify this behaves correctly).
"""
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from core.errors import JarvisError
from vision import read_screen as read_screen_module


@pytest.mark.asyncio
async def test_read_screen_uses_active_window_region_when_available():
    """The preferred, faster path: a specific app/dialog region instead
    of the whole screen. Full-screen capture must NOT be called when the
    region capture already succeeded."""
    with patch.object(read_screen_module, "capture_active_window_region", new=AsyncMock(return_value=Path("/tmp/region.png"))), \
         patch.object(read_screen_module, "capture_screen", new=AsyncMock()) as mock_full_screen, \
         patch.object(read_screen_module, "extract_text", new=AsyncMock(return_value="Error: port 3000 in use")):
        result = await read_screen_module.read_screen()

    assert result == "Error: port 3000 in use"
    mock_full_screen.assert_not_called()


@pytest.mark.asyncio
async def test_read_screen_falls_back_to_full_screen_when_region_unavailable():
    """When the active window's bounds can't be determined,
    capture_active_window_region returns None (not an error) — read_screen
    must fall back to the full-screen capture, not fail."""
    with patch.object(read_screen_module, "capture_active_window_region", new=AsyncMock(return_value=None)), \
         patch.object(read_screen_module, "capture_screen", new=AsyncMock(return_value=Path("/tmp/full.png"))) as mock_full_screen, \
         patch.object(read_screen_module, "extract_text", new=AsyncMock(return_value="Desktop text")):
        result = await read_screen_module.read_screen()

    assert result == "Desktop text"
    mock_full_screen.assert_called_once()


@pytest.mark.asyncio
async def test_read_screen_raises_when_no_text_found():
    with patch.object(read_screen_module, "capture_active_window_region", new=AsyncMock(return_value=Path("/tmp/fake.png"))), \
         patch.object(read_screen_module, "extract_text", new=AsyncMock(return_value="   ")):
        with pytest.raises(JarvisError):
            await read_screen_module.read_screen()


@pytest.mark.asyncio
async def test_read_screen_truncates_very_long_text():
    long_text = "x" * 10000
    with patch.object(read_screen_module, "capture_active_window_region", new=AsyncMock(return_value=Path("/tmp/fake.png"))), \
         patch.object(read_screen_module, "extract_text", new=AsyncMock(return_value=long_text)):
        result = await read_screen_module.read_screen()
    assert len(result) < len(long_text)
    assert result.endswith("(truncated)")
