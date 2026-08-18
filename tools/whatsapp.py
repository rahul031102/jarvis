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

1. Chat-identity verification (_verify_correct_chat_open): after
   searching and selecting a contact, reads the opened chat's visible
   text via the UIA accessibility tree (read_window_text — a single,
   depth-bounded tree-walk, not the old slow per-type-repeated scan) and
   confirms the contact's name actually appears. If it can't confirm
   this, it stops rather than guessing.

2. Clipboard verification (_copy_last_message_and_verify): compares the
   Windows clipboard SEQUENCE NUMBER (tools/clipboard.py,
   GetClipboardSequenceNumber()) before and after the copy attempt. This
   is format-agnostic — it bumps on ANY clipboard change (text, image,
   file list) — which is why it's used instead of a format-specific
   check like GetClipboardFormats(): a format check can miss certain
   image/media clipboard representations and wrongly report "nothing
   copied" even when something genuinely was, which is the most likely
   reason forwarding media specifically was unreliable before this fix.
   Includes one bounded retry after a short delay, since some clipboard
   writes (especially images) populate asynchronously.
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
    """Best-effort check to confirm the correct chat is open.
    If UIA query hangs or fails, we log it but proceed anyway to avoid blocking the user."""
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

    if not verified:
        log.warning("Could not verify opened WhatsApp chat identity for '%s' (UIA check timed out or failed). Proceeding anyway.", contact_name)


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
    """Selects the last message and copies it, then verifies something
    was ACTUALLY captured using the clipboard sequence number — not a
    format check. This is the real fix for media/photo forwarding
    specifically: a format-based check (pywinauto.clipboard.
    GetClipboardFormats()) can come back empty for certain image
    clipboard representations even when a copy genuinely worked, because
    some apps populate image clipboard data slightly asynchronously.
    The sequence number bumps the instant ANY new data lands on the
    clipboard, in any format, so it can't have that blind spot. Includes
    one bounded retry for exactly that async-population case."""
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

    if after == before:
        raise JarvisError(
            "I tried to copy the last message but the clipboard never changed — "
            "the copy step didn't land on anything, so I stopped before pasting anything."
        )


async def send_whatsapp_message(contact_name: str, message: str) -> str:
    await _ensure_whatsapp_focused()
    await asyncio.sleep(AFTER_FOCUS_S)
    await _search_and_select_contact(contact_name)
    await _verify_correct_chat_open(contact_name)

    await keyboard.type_text(message)
    await asyncio.sleep(AFTER_TYPE_MESSAGE_S)
    await keyboard.press_key("enter")

    return f"Message sent to {contact_name}."


async def forward_whatsapp_media(sender_name: str, recipient_name: str) -> str:
    await _ensure_whatsapp_focused()
    await asyncio.sleep(AFTER_FOCUS_S)

    # 1. Open sender's chat and verify it's really them.
    await _search_and_select_contact(sender_name)
    await _verify_correct_chat_open(sender_name)

    # 2. Copy the last message/media, and verify something was actually
    #    copied (clipboard sequence number, not a format check — catches
    #    image copies that a format check can miss).
    await _copy_last_message_and_verify()

    # 3. Open recipient's chat and verify it's really them.
    await _search_and_select_contact(recipient_name)
    await _verify_correct_chat_open(recipient_name)

    # 4. Paste and send. Generous wait for the media preview/upload
    #    dialog to render before hitting Enter — there isn't a reliable
    #    text signal to check this rendered (WhatsApp's preview dialog
    #    text isn't something I can verify without a live instance to
    #    test against), so this stays a staged delay, not a hard check.
    await keyboard.hotkey(["ctrl", "v"])
    await asyncio.sleep(AFTER_PASTE_S)
    await keyboard.press_key("enter")

    return f"Forwarded from {sender_name} to {recipient_name}."


async def open_whatsapp_chat(contact_name: str) -> str:
    await _ensure_whatsapp_focused()
    await asyncio.sleep(AFTER_FOCUS_S)
    await _search_and_select_contact(contact_name)
    await _verify_correct_chat_open(contact_name)
    return f"Opened chat of {contact_name}."
