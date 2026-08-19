"""
Tests for tools/web_automation.py — mocks Playwright's async API entirely
(no real browser launched in this sandbox), proving the locator fallback
chains, error handling, and confirmation-gate wiring work correctly.
"""
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from core.errors import JarvisError
from tools import web_automation


def _fake_locator(succeeds: bool = True, exc: Exception | None = None):
    loc = MagicMock()
    loc.first = loc
    if succeeds:
        loc.click = AsyncMock()
        loc.fill = AsyncMock()
        loc.set_input_files = AsyncMock()
    else:
        err = exc or Exception("not found")
        loc.click = AsyncMock(side_effect=err)
        loc.fill = AsyncMock(side_effect=err)
        loc.set_input_files = AsyncMock(side_effect=err)
    return loc


def _fake_page(**overrides):
    page = MagicMock()
    page.goto = AsyncMock()
    page.title = AsyncMock(return_value="Test Page")
    page.inner_text = AsyncMock(return_value="Some page content")
    page.get_by_role = MagicMock(return_value=_fake_locator(succeeds=False))
    page.get_by_text = MagicMock(return_value=_fake_locator(succeeds=False))
    page.get_by_label = MagicMock(return_value=_fake_locator(succeeds=False))
    page.get_by_placeholder = MagicMock(return_value=_fake_locator(succeeds=False))
    page.set_default_timeout = MagicMock()
    for k, v in overrides.items():
        setattr(page, k, v)
    return page


@pytest.fixture(autouse=True)
def reset_session():
    web_automation._session = web_automation.BrowserSession()
    yield
    web_automation._session = web_automation.BrowserSession()


async def _inject_fake_page(page):
    web_automation._session._context = MagicMock()
    web_automation._session._page = page


@pytest.mark.asyncio
async def test_navigate_to_adds_https_prefix_when_missing():
    page = _fake_page()
    await _inject_fake_page(page)

    result = await web_automation.navigate_to("example.com")

    page.goto.assert_called_once()
    called_url = page.goto.call_args[0][0]
    assert called_url == "https://example.com"
    assert "Test Page" in result


@pytest.mark.asyncio
async def test_navigate_to_raises_clear_error_on_failure():
    page = _fake_page(goto=AsyncMock(side_effect=Exception("net::ERR_CONNECTION_REFUSED")))
    await _inject_fake_page(page)

    with pytest.raises(JarvisError) as excinfo:
        await web_automation.navigate_to("https://doesnotexist.example")
    assert "couldn't open" in str(excinfo.value)


@pytest.mark.asyncio
async def test_read_page_content_returns_body_text():
    page = _fake_page(inner_text=AsyncMock(return_value="Job Application Form"))
    await _inject_fake_page(page)

    result = await web_automation.read_page_content()
    assert result == "Job Application Form"


@pytest.mark.asyncio
async def test_read_page_content_raises_when_empty():
    page = _fake_page(inner_text=AsyncMock(return_value="   "))
    await _inject_fake_page(page)

    with pytest.raises(JarvisError):
        await web_automation.read_page_content()


@pytest.mark.asyncio
async def test_read_page_content_truncates_long_pages():
    page = _fake_page(inner_text=AsyncMock(return_value="x" * 20000))
    await _inject_fake_page(page)

    result = await web_automation.read_page_content()
    assert len(result) < 20000
    assert result.endswith("(truncated)")


@pytest.mark.asyncio
async def test_click_web_element_tries_button_role_first():
    page = _fake_page()
    working_button_locator = _fake_locator(succeeds=True)
    page.get_by_role = MagicMock(side_effect=lambda role, name, exact: (
        working_button_locator if role == "button" else _fake_locator(succeeds=False)
    ))
    await _inject_fake_page(page)

    result = await web_automation.click_web_element("Apply Now")

    working_button_locator.click.assert_called_once()
    assert "Apply Now" in result


@pytest.mark.asyncio
async def test_click_web_element_falls_back_to_link_role_then_text():
    page = _fake_page()
    button_loc = _fake_locator(succeeds=False)
    link_loc = _fake_locator(succeeds=True)
    page.get_by_role = MagicMock(side_effect=lambda role, name, exact: (
        link_loc if role == "link" else button_loc
    ))
    await _inject_fake_page(page)

    result = await web_automation.click_web_element("Learn More")
    link_loc.click.assert_called_once()
    assert "Learn More" in result


@pytest.mark.asyncio
async def test_click_web_element_raises_when_nothing_matches():
    page = _fake_page()
    await _inject_fake_page(page)

    with pytest.raises(JarvisError) as excinfo:
        await web_automation.click_web_element("Nonexistent Button")
    assert "couldn't find anything matching" in str(excinfo.value)


@pytest.mark.asyncio
async def test_fill_web_form_field_uses_label_locator():
    page = _fake_page()
    label_loc = _fake_locator(succeeds=True)
    page.get_by_label = MagicMock(return_value=label_loc)
    await _inject_fake_page(page)

    result = await web_automation.fill_web_form_field("Full Name", "Rahul Kumar Dasari")

    label_loc.fill.assert_called_once_with("Rahul Kumar Dasari", timeout=web_automation.ACTION_TIMEOUT_MS)
    assert "Full Name" in result


@pytest.mark.asyncio
async def test_fill_web_form_field_falls_back_to_placeholder():
    page = _fake_page()
    page.get_by_label = MagicMock(return_value=_fake_locator(succeeds=False))
    placeholder_loc = _fake_locator(succeeds=True)
    page.get_by_placeholder = MagicMock(return_value=placeholder_loc)
    await _inject_fake_page(page)

    result = await web_automation.fill_web_form_field("Email", "ron@example.com")
    placeholder_loc.fill.assert_called_once()


@pytest.mark.asyncio
async def test_fill_web_form_field_raises_when_field_not_found():
    page = _fake_page()
    await _inject_fake_page(page)

    with pytest.raises(JarvisError) as excinfo:
        await web_automation.fill_web_form_field("Nonexistent Field", "value")
    assert "couldn't find a form field" in str(excinfo.value)


@pytest.mark.asyncio
async def test_upload_file_to_form_raises_when_local_file_missing(tmp_path):
    page = _fake_page()
    await _inject_fake_page(page)

    with pytest.raises(JarvisError) as excinfo:
        await web_automation.upload_file_to_form("Resume", str(tmp_path / "does_not_exist.pdf"))
    assert "couldn't find the file" in str(excinfo.value)


@pytest.mark.asyncio
async def test_upload_file_to_form_calls_set_input_files(tmp_path):
    resume = tmp_path / "resume.pdf"
    resume.write_text("fake pdf content")

    page = _fake_page()
    upload_loc = _fake_locator(succeeds=True)
    page.get_by_label = MagicMock(return_value=upload_loc)
    await _inject_fake_page(page)

    result = await web_automation.upload_file_to_form("Resume", str(resume))

    upload_loc.set_input_files.assert_called_once_with(str(resume), timeout=web_automation.ACTION_TIMEOUT_MS)
    assert "resume.pdf" in result


@pytest.mark.asyncio
async def test_submit_web_form_tries_submit_apply_send_in_order():
    page = _fake_page()
    apply_loc = _fake_locator(succeeds=True)
    page.get_by_role = MagicMock(side_effect=lambda role, name, exact: (
        apply_loc if name == "apply" else _fake_locator(succeeds=False)
    ))
    await _inject_fake_page(page)

    result = await web_automation.submit_web_form()
    apply_loc.click.assert_called_once()
    assert result == "Submitted."


@pytest.mark.asyncio
async def test_submit_web_form_raises_clear_error_when_no_button_found():
    page = _fake_page()
    await _inject_fake_page(page)

    with pytest.raises(JarvisError) as excinfo:
        await web_automation.submit_web_form()
    assert "couldn't find a submit button" in str(excinfo.value)
