"""
Real browser automation via Playwright — navigating, reading actual page
content, clicking real elements, filling form fields, uploading files.

This is deliberately separate from tools/browser.py (which just opens
URLs/searches via the OS default browser) and tools/windows.py (UIA-based
control of native Windows apps, including Chrome's own chrome — tab
strip, address bar — but NOT reliable for arbitrary web PAGE content).
Playwright talks directly to the page's DOM/accessibility tree through
the browser itself, which is far more reliable for web content than
routing through Windows' UIA layer the way WhatsApp automation has to.

Architecture: a single persistent, VISIBLE (not headless) Chromium
profile, launched once and reused for the lifetime of the app — no
repeated browser startup cost per tool call. It's a separate profile
from your regular Chrome (own directory under data/), so it won't
conflict with an already-running Chrome instance, and logins/cookies
persist across JARVIS restarts once you sign in inside it. It runs
visibly on purpose: you should be able to see what JARVIS is doing to a
page, and the first time you use a site that needs a login, you sign in
yourself in that same window — JARVIS doesn't and shouldn't handle your
passwords.

Honesty about reliability: arbitrary third-party websites don't share a
common structure. get_by_label/get_by_placeholder/get_by_role locators
(used here) are Playwright's most robust option — matching on what a
human would actually see, not brittle CSS selectors — but there is no
technique that reliably finds "the right field" on every possible site.
When a field can't be found with reasonable confidence, these functions
raise a clear error rather than guessing at the wrong element or leaving
something silently blank.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from core.errors import JarvisError
from core.logging_setup import log

PROFILE_DIR = Path("data/browser_profile")
NAVIGATION_TIMEOUT_MS = 20000
ACTION_TIMEOUT_MS = 8000
MAX_PAGE_TEXT_CHARS = 6000


class BrowserSession:
    """Owns the single persistent Playwright browser context for the
    whole app lifetime. Lazily started on first use — matches this
    project's existing pattern (STT/TTS/wake-word models are all
    lazy-loaded once, not re-initialized per call)."""

    def __init__(self) -> None:
        self._playwright = None
        self._context = None
        self._page = None
        self._lock = asyncio.Lock()

    async def _ensure_started(self):
        async with self._lock:
            if self._context is not None:
                return
            from playwright.async_api import async_playwright

            PROFILE_DIR.mkdir(parents=True, exist_ok=True)
            self._playwright = await async_playwright().start()
            try:
                self._context = await self._playwright.chromium.launch_persistent_context(
                    user_data_dir=str(PROFILE_DIR),
                    channel="chrome",
                    headless=False,  # visible on purpose — see module docstring
                    viewport={"width": 1280, "height": 900},
                    ignore_default_args=["--enable-automation"],
                    args=["--disable-blink-features=AutomationControlled"],
                )
            except Exception as exc:
                await self._playwright.stop()
                self._playwright = None
                raise JarvisError(
                    "I couldn't start the browser automation profile.",
                    technical_detail=str(exc),
                )
            self._page = self._context.pages[0] if self._context.pages else await self._context.new_page()
            self._page.set_default_timeout(ACTION_TIMEOUT_MS)
            log.info("[web] Persistent browser context started.")

    async def get_page(self):
        await self._ensure_started()
        return self._page

    async def close(self) -> None:
        async with self._lock:
            if self._context is not None:
                await self._context.close()
                self._context = None
            if self._playwright is not None:
                await self._playwright.stop()
                self._playwright = None


_session = BrowserSession()


async def navigate_to(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    page = await _session.get_page()
    try:
        await page.goto(url, timeout=NAVIGATION_TIMEOUT_MS, wait_until="domcontentloaded")
    except Exception as exc:
        raise JarvisError(f"I couldn't open {url}.", technical_detail=str(exc))
    log.info("[web] Navigated to %s (title: %s)", url, await page.title())
    return f"Opened {await page.title()}."


async def read_page_content() -> str:
    """Returns the visible text of the current page — real DOM text, not
    OCR, so it's exact and doesn't need the OCR speed/quality tradeoffs
    that vision/ocr.py has to make for actual screenshots."""
    page = await _session.get_page()
    try:
        text = await page.inner_text("body")
    except Exception as exc:
        raise JarvisError("I couldn't read this page's content.", technical_detail=str(exc))
    text = text.strip()
    if not text:
        raise JarvisError("This page doesn't appear to have any readable text.")
    if len(text) > MAX_PAGE_TEXT_CHARS:
        text = text[:MAX_PAGE_TEXT_CHARS] + "... (truncated)"
    return text


async def click_web_element(text: str) -> str:
    """Clicks a button or link by its visible text — Playwright's
    get_by_role/get_by_text locators, which match what a person would
    actually see, not a CSS selector guess."""
    page = await _session.get_page()

    for attempt in (
        lambda: page.get_by_role("button", name=text, exact=False),
        lambda: page.get_by_role("link", name=text, exact=False),
        lambda: page.get_by_text(text, exact=False),
    ):
        try:
            locator = attempt().first
            await locator.click(timeout=ACTION_TIMEOUT_MS)
            log.info("[web] Clicked element matching '%s'.", text)
            return f"Clicked '{text}'."
        except Exception:
            continue

    raise JarvisError(f"I couldn't find anything matching '{text}' to click on this page.")


async def fill_web_form_field(label: str, value: str) -> str:
    """Fills a form field found by its visible label or placeholder text
    — NOT by guessing an HTML 'name' attribute, which varies wildly
    between sites and isn't something a person reading the page would
    know. If nothing matches with reasonable confidence, this refuses
    rather than filling the wrong field."""
    page = await _session.get_page()

    for attempt in (
        lambda: page.get_by_label(label, exact=False),
        lambda: page.get_by_placeholder(label, exact=False),
    ):
        try:
            locator = attempt().first
            await locator.fill(value, timeout=ACTION_TIMEOUT_MS)
            log.info("[web] Filled field matching '%s'.", label)
            return f"Filled '{label}'."
        except Exception:
            continue

    raise JarvisError(f"I couldn't find a form field matching '{label}' on this page.")


async def upload_file_to_form(label: str, file_path: str) -> str:
    path = Path(file_path).expanduser()
    if not path.exists():
        raise JarvisError(f"I couldn't find the file {file_path}.")

    page = await _session.get_page()
    try:
        locator = page.get_by_label(label, exact=False).first
        await locator.set_input_files(str(path), timeout=ACTION_TIMEOUT_MS)
    except Exception as exc:
        raise JarvisError(
            f"I couldn't find an upload field matching '{label}' on this page.",
            technical_detail=str(exc),
        )
    log.info("[web] Uploaded %s to field matching '%s'.", path.name, label)
    return f"Uploaded {path.name}."


async def submit_web_form() -> str:
    """Only ever reached after explicit user confirmation via
    core/security.py — submit_web_form is registered in DANGEROUS_TOOLS.
    This is the one irreversible step in the whole flow, matching exactly
    what was asked for: never submit anything without approval first."""
    page = await _session.get_page()

    for attempt in (
        lambda: page.get_by_role("button", name="submit", exact=False),
        lambda: page.get_by_role("button", name="apply", exact=False),
        lambda: page.get_by_role("button", name="send", exact=False),
    ):
        try:
            locator = attempt().first
            await locator.click(timeout=ACTION_TIMEOUT_MS)
            log.info("[web] Submitted form.")
            return "Submitted."
        except Exception:
            continue

    raise JarvisError(
        "I couldn't find a submit button on this page — tell me its exact "
        "label and I'll click it with click_web_element instead."
    )
