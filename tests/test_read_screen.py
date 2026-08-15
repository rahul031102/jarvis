"""
Tests the read_screen tool's logic (empty-result handling, truncation)
with the actual screen capture and OCR calls mocked out — no real
screenshot or Tesseract binary needed to verify this behaves correctly.
"""
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from core.errors import JarvisError
from vision import read_screen as read_screen_module


@pytest.mark.asyncio
async def test_read_screen_returns_extracted_text():
    with patch.object(read_screen_module, "capture_screen", new=AsyncMock(return_value=Path("/tmp/fake.png"))), \
         patch.object(read_screen_module, "extract_text", new=AsyncMock(return_value="Error: port 3000 in use")):
        result = await read_screen_module.read_screen()
    assert result == "Error: port 3000 in use"


@pytest.mark.asyncio
async def test_read_screen_raises_when_no_text_found():
    with patch.object(read_screen_module, "capture_screen", new=AsyncMock(return_value=Path("/tmp/fake.png"))), \
         patch.object(read_screen_module, "extract_text", new=AsyncMock(return_value="   ")):
        with pytest.raises(JarvisError):
            await read_screen_module.read_screen()


@pytest.mark.asyncio
async def test_read_screen_truncates_very_long_text():
    long_text = "x" * 10000
    with patch.object(read_screen_module, "capture_screen", new=AsyncMock(return_value=Path("/tmp/fake.png"))), \
         patch.object(read_screen_module, "extract_text", new=AsyncMock(return_value=long_text)):
        result = await read_screen_module.read_screen()
    assert len(result) < len(long_text)
    assert result.endswith("(truncated)")
