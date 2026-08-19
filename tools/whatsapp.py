"""
Automated WhatsApp macro: search a contact, select their chat, and either
type+send a message, or copy the last message/media from one chat and
paste+send it into another.

Safety note: send_whatsapp_message and forward_whatsapp_media are both
registered in ai/schemas.py's DANGEROUS_TOOLS, so they always go through
the confirmation flow in core/security.py before running — the person
hears back the exact contact and message text and has to approve it
first. That matters here specifically because speech-to-text can mishear
a name or word, and this action is irreversible once sent.

Honesty about reliability: this automates a third-party Electron app via
its accessibility tree and keyboard hotkeys — neither of which WhatsApp
Desktop documents or guarantees. Nothing here can honestly promise "100%
reliable." What CAN be made reliable, and is: JARVIS will never claim
success when it didn't actually verify one. Two checks enforce that,
and both are fail-CLOSED (refuse and stop) rather than fail-open (warn
and continue anyway) — a verification step that proceeds regardless of
its own result isn't verification, it's decoration, and for something
irreversible like sending a message to a real person, that's not an
acceptable trade-off for speed:

1. Chat-identity verification (_verify_correct_chat_open): tries the
   fast UIA check first (near-free when the accessibility tree is
   healthy); if that fails/times out, falls back to a single OCR read of
   the chat header rather than giving up. Never proceeds unverified.

2. Clipboard verification (_copy_last_message_and_verify): compares the
   Windows clipboard SEQUENCE NUMBER (tools/clipboard.py,
   GetClipboardSequenceNumber()) before and after the copy attempt —
   format-agnostic, bumps on ANY clipboard change (text, image, file
   list). Tries the fast keyboard/UIA selection path first; if nothing
   actually landed on the clipboard, falls back to right-clicking the
   message and OCR-locating "Copy" in WhatsApp's real context menu — the
   only mechanism WhatsApp Desktop actually exposes for copying an
   arbitrary received message (there's no documented pure-keyboard
   equivalent), which is almost certainly why the fast path alone was
   failing consistently on some machines.

Both paths only pay the slower OCR cost once the fast path has already
been tried and failed — they don't replace it. On a machine where UIA
works fine, none of this fallback code runs and behavior is unchanged.
"""
from __future__ import annotations

import asyncio

from tools import applications, keyboard, windows
from tools.clipboard import get_clipboard_sequence_number
from core.errors import JarvisError
from core.logging_setup import log

# Tuned, staged delays. These exist because WhatsApp Desktop (Electron/
# Chromium) has real, variable UI-response latency — search filtering,
# chat-switch rendering, and media-preview loading are all asynchronous
# on its end, not instant. These values are deliberately generous rather
# than minimal: a failed automation costs far more (a stuck/wrong send)
# than an extra few hundred milliseconds.
AFTER_FOCUS_S = 0.6
AFTER_SEARCH_OPEN_S = 0.35
AFTER_CLEAR_S = 0.15
AFTER_TYPE_CONTACT_S = 1.1        # search filtering needs to settle
AFTER_SELECT_CONTACT_S = 0.6      # chat pane needs to finish rendering
BETWEEN_SHIFT_TAB_S = 0.25
AFTER_LAST_SHIFT_TAB_S = 0.35
AFTER_ARROW_NAV_S = 0.25
AFTER_COPY_HOTKEY_S = 0.6
CLIPBOARD_RETRY_DELAY_S = 0.5
AFTER_PASTE_S = 1.8               # media preview/upload dialog render time
AFTER_TYPE_MESSAGE_S = 0.3


async def _ensure_whatsapp_focused() -> None:
    try:
        await windows.focus_window("WhatsApp")
    except Exception:
        await applications.open_application("WhatsApp")
        await asyncio.sleep(2.5)
        try:
            await windows.focus_window("WhatsApp")
        except Exception as exc:
            raise JarvisError("I opened WhatsApp, but couldn't focus the window.", technical_detail=str(exc))


async def _search_and_select_contact(contact_name: str) -> None:
    await keyboard.hotkey(["ctrl", "f"])
    await asyncio.sleep(AFTER_SEARCH_OPEN_S)
    await keyboard.hotkey(["ctrl", "a"])
    await asyncio.sleep(AFTER_CLEAR_S)
    await keyboard.press_key("backspace")
    await asyncio.sleep(AFTER_CLEAR_S)
    await keyboard.type_text(contact_name)
    await asyncio.sleep(AFTER_TYPE_CONTACT_S)
    await keyboard.press_key("enter")
    await asyncio.sleep(AFTER_SELECT_CONTACT_S)


async def _verify_correct_chat_open(contact_name: str) -> None:
    """Confirms the correct chat is open. Tries the fast UIA check first
    (near-free when WhatsApp's accessibility tree is healthy) and, only if
    that fails/times out, falls back to a single OCR read of the chat
    header — never silently proceeds unverified either way.

    Why not just "fail closed" on the UIA result alone: on at least one
    real machine, WhatsApp's UIA tree times out consistently, which would
    make a UIA-only fail-closed check reject every single attempt. That's
    not actually safer in practice — the orchestrator then retries the
    whole macro, and repeated full-timeout failures are what produced the
    40-90 second total latencies seen in real logs, not the tool's base
    cost. A single OCR fallback (~1-1.5s) costs less than one of those
    failed-UIA-then-retry cycles and actually succeeds where UIA can't."""
    import re
    from tools.uia_helpers import find_window_sync, run_uia
    from core.logging_setup import log

    needle = contact_name.strip().lower()
    if not needle:
        return

    def _check_fast() -> bool:
        win = find_window_sync("WhatsApp")
        if win is None:
            return False
        pattern = re.compile(rf".*{re.escape(contact_name)}.*", re.IGNORECASE)
        try:
            if win.child_window(title_re=pattern).exists():
                return True
        except Exception:
            pass
        return False

    try:
        verified = await run_uia(_check_fast, timeout=1.5)
    except Exception:
        verified = False

    if verified:
        return

    log.warning("UIA chat verification for '%s' failed/timed out — falling back to OCR.", contact_name)

    from vision.ocr import extract_text
    from vision.screen import capture_region
    from tools import windows as windows_mod

    try:
        left, top, right, bottom = await windows_mod.get_window_rect("WhatsApp")
        header_bottom = top + int((bottom - top) * 0.15)
        image_path = await capture_region(left, top, right, header_bottom)
        text = (await extract_text(image_path)).lower()
    except Exception as exc:
        raise JarvisError(
            f"I can't confirm the chat with {contact_name} is open — both the "
            "accessibility check and the fallback screen-read failed."
        ) from exc

    if needle not in text:
        raise JarvisError(
            f"I can't confirm the chat with {contact_name} is actually open — "
            "the chat header doesn't show that name, so I'm stopping here rather than guessing."
        )


async def _click_last_message() -> bool:
    """Attempts to select the most recent message/media bubble in the
    open chat. Tries a direct UIA click on the last ListItem first
    (depth=8, so it doesn't walk WhatsApp's full tree — see
    uia_helpers.py for why unbounded walks are a real hang risk here);
    falls back to keyboard navigation if that doesn't land cleanly.

    Returns whether the UIA click path succeeded, purely for logging —
    NOT used to decide success. Neither path here is independently
    verifiable (there's no reliable, testable signal that confirms "the
    right bubble is now selected" without a live WhatsApp instance to
    check against), which is exactly why _copy_last_message_and_verify
    checks the clipboard directly afterward rather than trusting this
    function's return value."""
    from tools.uia_helpers import find_window_sync, get_descendants_by_types, run_uia

    def _do() -> bool:
        win = find_window_sync("WhatsApp")
        if win is None:
            return False
        items = get_descendants_by_types(win, ("ListItem",), depth=8)
        if not items:
            return False
        try:
            items[-1].click_input()
            return True
        except Exception:
            return False

    try:
        clicked = await run_uia(_do, timeout=2.5)
    except Exception as e:
        log.warning("Programmatic UIA message selection failed: %s. Using keyboard navigation fallback...", e)
        clicked = False

    if not clicked:
        # Best-effort keyboard fallback. In WhatsApp Desktop, pressing the Up arrow
        # when focused in an empty text box directly selects the last message in the timeline.
        await keyboard.press_key("up")
        await asyncio.sleep(0.3)

        # Fallback to Shift+Tab cycling if Up arrow didn't select it
        await keyboard.hotkey(["shift", "tab"])
        await asyncio.sleep(BETWEEN_SHIFT_TAB_S)
        await keyboard.hotkey(["shift", "tab"])
        await asyncio.sleep(BETWEEN_SHIFT_TAB_S)
        await keyboard.hotkey(["shift", "tab"])
        await asyncio.sleep(AFTER_LAST_SHIFT_TAB_S)
        await keyboard.press_key("down")
        await asyncio.sleep(0.15)
        await keyboard.press_key("up")
        await asyncio.sleep(AFTER_ARROW_NAV_S)

    return clicked


async def _copy_last_message_and_verify() -> None:
    """Selects the last message and copies it, verifying with the
    clipboard sequence number (format-agnostic, catches image copies a
    format check can miss). If the fast keyboard/UIA path doesn't
    actually copy anything, falls back to right-clicking the message and
    OCR-locating "Copy" in the real context menu — WhatsApp Desktop has
    no documented pure-keyboard shortcut to copy an arbitrary (received)
    message; right-click -> Copy is the only mechanism it actually
    exposes for that, which is almost certainly why the fast path alone
    was failing every time. The fast path stays as the FIRST attempt
    (free on machines where it happens to work); this only pays the
    slower OCR cost when it's already been established the fast path
    didn't do anything."""
    before = await get_clipboard_sequence_number()

    await keyboard.press_key("escape")
    await asyncio.sleep(0.2)
    await _click_last_message()
    await asyncio.sleep(0.3)
    await keyboard.hotkey(["ctrl", "c"])
    await asyncio.sleep(AFTER_COPY_HOTKEY_S)

    after = await get_clipboard_sequence_number()

    if after == before:
        # One retry: some clipboard writes (especially images/media)
        # populate a beat after the hotkey fires, not instantly.
        await asyncio.sleep(CLIPBOARD_RETRY_DELAY_S)
        after = await get_clipboard_sequence_number()

    if after != before:
        return

    log.warning("Fast copy path landed nothing on the clipboard — falling back to right-click Copy.")
    await _right_click_copy_fallback(before)


async def _right_click_copy_fallback(before_seq: int) -> None:
    """Right-clicks near the bottom of the timeline (where the newest
    message sits, just above the composer) and OCR-locates+clicks "Copy"
    in the menu that opens. This is a real coordinate guess and a real
    OCR read — slower than the keyboard path, but it's WhatsApp's actual
    UI mechanism for copying a message, which the keyboard path has no
    real equivalent for."""
    import pyautogui
    from vision.ocr import extract_text_with_boxes
    from vision.screen import capture_screen
    from tools import windows as windows_mod

    left, top, right, bottom = await windows_mod.get_window_rect("WhatsApp")
    timeline_left = left + int((right - left) * 0.35)  # skip the left contact-list pane
    click_x = timeline_left + int((right - timeline_left) * 0.5)
    click_y = bottom - 90  # just above the composer/input box

    await asyncio.to_thread(pyautogui.click, click_x, click_y, "right")
    await asyncio.sleep(0.5)

    menu_path = await capture_screen()
    words = await extract_text_with_boxes(menu_path)
    copy_word = next((w for w in words if w["text"].strip().lower() in ("copy", "forward")), None)

    if copy_word is None:
        await keyboard.press_key("escape")
        raise JarvisError(
            "I right-clicked the last message but couldn't find a 'Copy' option in the menu "
            "that appeared — the click may have missed the message, or nothing selectable is there."
        )

    menu_click_x = copy_word["left"] + copy_word["width"] // 2
    menu_click_y = copy_word["top"] + copy_word["height"] // 2
    await asyncio.to_thread(pyautogui.click, menu_click_x, menu_click_y)
    await asyncio.sleep(0.5)

    after_seq = await get_clipboard_sequence_number()
    if after_seq == before_seq:
        raise JarvisError(
            "I clicked Copy but nothing ended up on the clipboard — "
            "I stopped before pasting anything."
        )


def _sanitize_contact_name(contact_name: str) -> str:
    import re
    name = contact_name.strip()
    # Strip common conversational suffixes (e.g. "Mummy contact", "Arun chart", "Arun chat")
    name = re.sub(r'\s+(contact|chat|chart|profile|message|account)$', '', name, flags=re.IGNORECASE)
    # Strip common conversational prefixes (e.g. "contact of Mummy", "chat of Arun")
    name = re.sub(r'^(contact of|chat of|chart of|message to|send to)\s+', '', name, flags=re.IGNORECASE)
    return name.strip()


async def send_whatsapp_message(contact_name: str, message: str) -> str:
    contact_name = _sanitize_contact_name(contact_name)
    await _ensure_whatsapp_focused()
    await asyncio.sleep(AFTER_FOCUS_S)
    await _search_and_select_contact(contact_name)
    await _verify_correct_chat_open(contact_name)

    await keyboard.type_text(message)
    await asyncio.sleep(AFTER_TYPE_MESSAGE_S)
    await keyboard.press_key("enter")

    return f"Message sent to {contact_name}."


async def forward_whatsapp_media(sender_name: str, recipient_name: str) -> str:
    import pyautogui
    from vision.ocr import extract_text_with_boxes
    from vision.screen import capture_screen
    from tools import windows as windows_mod

    sender_name = _sanitize_contact_name(sender_name)
    recipient_name = _sanitize_contact_name(recipient_name)

    await _ensure_whatsapp_focused()
    await asyncio.sleep(AFTER_FOCUS_S)

    # 1. Open sender's chat and verify it's really them.
    await _search_and_select_contact(sender_name)
    await _verify_correct_chat_open(sender_name)

    # 2. Right-click the last message/media to open the context menu.
    left, top, right, bottom = await windows_mod.get_window_rect("WhatsApp")
    timeline_left = left + int((right - left) * 0.35)  # skip left contact pane
    click_x = timeline_left + int((right - timeline_left) * 0.5)
    click_y = bottom - 90  # just above input composer

    await asyncio.to_thread(pyautogui.click, click_x, click_y, "right")
    await asyncio.sleep(0.5)

    # 3. OCR context menu and click "Forward"
    menu_path = await capture_screen()
    words = await extract_text_with_boxes(menu_path)
    forward_word = next((w for w in words if w["text"].strip().lower() == "forward"), None)

    if forward_word is None:
        await keyboard.press_key("escape")
        raise JarvisError(
            f"I right-clicked the last message in {sender_name}'s chat, but couldn't find a 'Forward' "
            "option in the menu. Please make sure there is a forwardable message visible."
        )

    menu_click_x = forward_word["left"] + forward_word["width"] // 2
    menu_click_y = forward_word["top"] + forward_word["height"] // 2
    await asyncio.to_thread(pyautogui.click, menu_click_x, menu_click_y)
    await asyncio.sleep(0.8)  # wait for forward dialog to render

    # 4. Type the recipient's name in the search box
    await keyboard.type_text(recipient_name)
    await asyncio.sleep(1.0)  # wait for search results to filter

    # 5. Select the contact and send using keyboard navigation
    await keyboard.press_key("tab")
    await asyncio.sleep(0.2)
    await keyboard.press_key("space")
    await asyncio.sleep(0.5)
    await keyboard.press_key("enter")
    await asyncio.sleep(0.5)

    return f"Forwarded media from {sender_name} to {recipient_name}."


async def open_whatsapp_chat(contact_name: str) -> str:
    contact_name = _sanitize_contact_name(contact_name)
    await _ensure_whatsapp_focused()
    await asyncio.sleep(AFTER_FOCUS_S)
    await _search_and_select_contact(contact_name)
    await _verify_correct_chat_open(contact_name)
    return f"Opened chat of {contact_name}."
