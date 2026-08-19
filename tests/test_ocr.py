"""
Tests for vision/ocr.py's preprocessing — proves the downscale and
grayscale steps that were added for OCR speed actually do what they
claim (real Pillow image manipulation, not mocked), and that
extract_text wires everything together and passes the tuned PSM config
to Tesseract.
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from PIL import Image

from vision import ocr


def test_preprocess_converts_to_grayscale():
    color_image = Image.new("RGB", (400, 300), color=(255, 0, 0))
    result = ocr._preprocess(color_image)
    assert result.mode == "L"  # "L" = grayscale in Pillow


def test_preprocess_downscales_large_images():
    large_image = Image.new("RGB", (3840, 2160))  # 4K
    result = ocr._preprocess(large_image)
    assert max(result.size) <= ocr.MAX_OCR_DIMENSION


def test_preprocess_preserves_aspect_ratio_when_downscaling():
    large_image = Image.new("RGB", (4000, 2000))  # 2:1 aspect ratio
    result = ocr._preprocess(large_image)
    ratio_before = 4000 / 2000
    ratio_after = result.size[0] / result.size[1]
    assert abs(ratio_before - ratio_after) < 0.01


def test_preprocess_does_not_upscale_small_images():
    """A small image should NOT get scaled UP to MAX_OCR_DIMENSION — the
    cap is a ceiling, not a target size."""
    small_image = Image.new("RGB", (400, 300))
    result = ocr._preprocess(small_image)
    assert result.size == (400, 300)


def test_preprocess_image_at_exactly_the_cap_is_unchanged_in_size():
    image = Image.new("RGB", (ocr.MAX_OCR_DIMENSION, 900))
    result = ocr._preprocess(image)
    assert result.size[0] == ocr.MAX_OCR_DIMENSION


@pytest.mark.asyncio
async def test_extract_text_uses_tuned_psm_config(tmp_path):
    """Proves the sparse-text PSM mode is actually passed to Tesseract,
    not just documented as a good idea."""
    img_path = tmp_path / "test.png"
    Image.new("RGB", (200, 200)).save(img_path)

    fake_pytesseract = MagicMock()
    fake_pytesseract.image_to_string.return_value = "some extracted text"
    fake_pytesseract.TesseractNotFoundError = Exception

    with patch.dict("sys.modules", {"pytesseract": fake_pytesseract}):
        result = await ocr.extract_text(img_path)

    assert result == "some extracted text"
    call_kwargs = fake_pytesseract.image_to_string.call_args
    assert call_kwargs.kwargs.get("config") == ocr.TESSERACT_CONFIG
    assert "psm 11" in ocr.TESSERACT_CONFIG


@pytest.mark.asyncio
async def test_extract_text_preprocesses_before_ocr(tmp_path):
    """The image handed to Tesseract should be the preprocessed
    (grayscale, bounded) version, not the raw original."""
    img_path = tmp_path / "test.png"
    Image.new("RGB", (3840, 2160)).save(img_path)  # large, color

    fake_pytesseract = MagicMock()
    fake_pytesseract.image_to_string.return_value = "text"
    fake_pytesseract.TesseractNotFoundError = Exception

    with patch.dict("sys.modules", {"pytesseract": fake_pytesseract}):
        await ocr.extract_text(img_path)

    passed_image = fake_pytesseract.image_to_string.call_args[0][0]
    assert passed_image.mode == "L"
    assert max(passed_image.size) <= ocr.MAX_OCR_DIMENSION


@pytest.mark.asyncio
async def test_extract_text_raises_clear_error_when_tesseract_missing(tmp_path):
    img_path = tmp_path / "test.png"
    Image.new("RGB", (100, 100)).save(img_path)

    class FakeTesseractNotFoundError(Exception):
        pass

    fake_pytesseract = MagicMock()
    fake_pytesseract.TesseractNotFoundError = FakeTesseractNotFoundError
    fake_pytesseract.image_to_string.side_effect = FakeTesseractNotFoundError()

    from core.errors import JarvisError

    with patch.dict("sys.modules", {"pytesseract": fake_pytesseract}):
        with pytest.raises(JarvisError) as excinfo:
            await ocr.extract_text(img_path)

    assert "Tesseract" in str(excinfo.value)
