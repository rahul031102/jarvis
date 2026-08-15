"""
Tests tools/uia_helpers.py directly: the timeout wrapper actually times
out instead of hanging, and the retry-if-empty helper retries exactly
once (not zero, not infinitely).
"""
import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from core.errors import JarvisError
from tools import uia_helpers


@pytest.mark.asyncio
async def test_run_uia_returns_result_on_success():
    def fast_func():
        return "ok"

    result = await uia_helpers.run_uia(fast_func, timeout=1.0)
    assert result == "ok"


@pytest.mark.asyncio
async def test_run_uia_raises_jarvis_error_on_timeout():
    def slow_func():
        import time
        time.sleep(2)
        return "too late"

    with pytest.raises(JarvisError):
        await uia_helpers.run_uia(slow_func, timeout=0.1)


@pytest.mark.asyncio
async def test_with_retry_if_empty_retries_exactly_once_when_empty(monkeypatch):
    monkeypatch.setattr(uia_helpers, "RETRY_DELAY_S", 0.01)
    call_count = {"n": 0}

    def flaky_func():
        call_count["n"] += 1
        return []  # always empty, to prove it retries exactly once and stops

    result = await uia_helpers.with_retry_if_empty(flaky_func, is_empty=lambda r: not r)

    assert result == []
    assert call_count["n"] == 2  # initial attempt + exactly one retry


@pytest.mark.asyncio
async def test_with_retry_if_empty_does_not_retry_when_result_present(monkeypatch):
    monkeypatch.setattr(uia_helpers, "RETRY_DELAY_S", 0.01)
    call_count = {"n": 0}

    def good_func():
        call_count["n"] += 1
        return ["something"]

    result = await uia_helpers.with_retry_if_empty(good_func, is_empty=lambda r: not r)

    assert result == ["something"]
    assert call_count["n"] == 1  # no retry needed


@pytest.mark.asyncio
async def test_with_retry_if_empty_succeeds_on_second_attempt():
    """Simulates the real Chromium scenario: empty on first query, has
    content once the accessibility tree finishes activating."""
    call_count = {"n": 0}

    def lazy_tree_func():
        call_count["n"] += 1
        if call_count["n"] == 1:
            return []
        return ["now it's here"]

    result = await uia_helpers.with_retry_if_empty(lazy_tree_func, is_empty=lambda r: not r)

    assert result == ["now it's here"]
    assert call_count["n"] == 2


def test_find_window_sync_matches_by_fuzzy_title():
    win = MagicMock()
    win.window_text.return_value = "Untitled - Notepad"
    fake_desktop = MagicMock()
    fake_desktop.windows.return_value = [win]

    with patch.object(uia_helpers, "get_desktop", return_value=fake_desktop):
        result = uia_helpers.find_window_sync("notepad")

    assert result is win


def test_find_window_sync_returns_none_when_not_found():
    fake_desktop = MagicMock()
    fake_desktop.windows.return_value = []

    with patch.object(uia_helpers, "get_desktop", return_value=fake_desktop):
        result = uia_helpers.find_window_sync("nonexistent")

    assert result is None


def test_get_descendants_by_types_walks_once_and_filters_in_python():
    """The core fix: ONE call to win.descendants() regardless of how many
    types we're filtering for, with type-matching done in Python via
    friendly_class_name() afterward. This directly replaces the old
    'call descendants(control_type=X) once per type' pattern that caused
    the 40-60s WhatsApp/Chrome latency."""
    button = MagicMock()
    button.friendly_class_name.return_value = "Button"
    text = MagicMock()
    text.friendly_class_name.return_value = "Text"
    pane = MagicMock()
    pane.friendly_class_name.return_value = "Pane"  # not in either type set

    win = MagicMock()
    win.descendants.return_value = [button, text, pane]

    result = uia_helpers.get_descendants_by_types(win, ("Button", "Text"))

    assert win.descendants.call_count == 1
    assert button in result
    assert text in result
    assert pane not in result


def test_get_descendants_by_types_handles_broken_element_gracefully():
    """One element throwing on friendly_class_name() shouldn't break the
    whole scan — matches this codebase's pattern of per-element try/except
    everywhere else in the UIA tools."""
    good = MagicMock()
    good.friendly_class_name.return_value = "Button"
    broken = MagicMock()
    broken.friendly_class_name.side_effect = Exception("COM error")

    win = MagicMock()
    win.descendants.return_value = [broken, good]

    result = uia_helpers.get_descendants_by_types(win, ("Button",))

    assert result == [good]


def test_get_descendants_by_types_empty_when_descendants_call_fails():
    win = MagicMock()
    win.descendants.side_effect = Exception("app not responding")

    result = uia_helpers.get_descendants_by_types(win, ("Button",))

    assert result == []
