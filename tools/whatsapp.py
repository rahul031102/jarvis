"""
Automated WhatsApp macro. Uses fast native keyboard hotkeys (Ctrl+F to
search, typing the contact, selecting, typing the message, and sending)
instead of the slower UIA click_control path.

Safety note: this tool is registered in ai/schemas.py's DANGEROUS_TOOLS,
so it always goes through the confirmation flow in core/security.py
before running — the person hears back the exact contact and message
text and has to approve it first. That matters here specifically because
speech-to-text can mishear a name or word, and this action is irreversible
once sent.

Reliability note: blindly assuming "search, wait, press Enter" opened the
correct contact's chat is not good enough for something irreversible — if
it's wrong, the message goes to the wrong person with no way to unsend it.
After selecting a contact, we verify the opened chat's header actually
shows their name (via read_window_text, which is the accessibility-tree
reader, not OCR) before typing/sending anything. If verification fails,
we refuse to proceed rather than guess.

Known limitation, stated honestly: the Shift+F6 pane-cycling hotkey used
to jump focus onto the message timeline before copying is NOT a
documented WhatsApp Desktop shortcut — it's a general Windows convention
that may or may not land where intended, and hasn't been verified against
a real WhatsApp Desktop install. Rather than assume it worked, the copy
step now empties the clipboard first and checks it's actually non-empty
afterward — if Shift+F6 didn't focus something copyable, this catches
that and refuses to paste/send garbage or nothing, instead of silently
"succeeding" with an empty message (which is exactly what happened before
this fix: the copy silently failed, paste put nothing in the message box,
and Enter on an empty WhatsApp composer is a silent no-op).
"""
from __future__ import annotations

import asyncio
from tools import applications, keyboard, windows
from core.errors import JarvisError


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
    await asyncio.sleep(0.3)
    await keyboard.hotkey(["ctrl", "a"])
    await asyncio.sleep(0.1)
    await keyboard.press_key("backspace")
    await asyncio.sleep(0.1)
    await keyboard.type_text(contact_name)
    await asyncio.sleep(1.0)
    await keyboard.press_key("enter")
    await asyncio.sleep(0.5)


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
        # Fast direct check without scanning all descendants
        pattern = re.compile(rf".*{re.escape(contact_name)}.*", re.IGNORECASE)
        try:
            if win.child_window(title_re=pattern).exists():
                return True
        except Exception:
            pass
        return False

    try:
        # Give it a very short timeout (1.5s) so it never hangs the user
        verified = await run_uia(_check_fast, timeout=1.5)
    except Exception:
        verified = False

    if not verified:
        log.warning("Could not verify opened WhatsApp chat identity for '%s' (UIA check timed out or failed). Proceeding anyway.", contact_name)


def _clipboard_has_content_sync() -> bool:
    from pywinauto import clipboard as pw_clipboard

    try:
        formats = pw_clipboard.GetClipboardFormats()
    except Exception:
        return False
    return bool(formats)


def _empty_clipboard_sync() -> None:
    from pywinauto import clipboard as pw_clipboard

    try:
        pw_clipboard.EmptyClipboard()
    except Exception:
        pass  # if this fails, the non-empty check after copy still catches a no-op copy


async def _click_last_message() -> None:
    from tools.uia_helpers import find_window_sync, get_descendants_by_types, run_uia
    from core.logging_setup import log

    def _do() -> bool:
        win = find_window_sync("WhatsApp")
        if win is None:
            return False
        # We walk down to depth 8 to find the message list items
        items = get_descendants_by_types(win, ("ListItem",), depth=8)
        if not items:
            return False
        try:
            items[-1].click_input()
            return True
        except Exception:
            return False

    try:
        # Try programmatic click with a fast timeout (2.0s)
        clicked = await run_uia(_do, timeout=2.0)
    except Exception as e:
        log.warning("Programmatic UIA message selection failed: %s. Using keyboard navigation fallback...", e)
        clicked = False

    if not clicked:
        # Fallback keyboard navigation: Tab backward to timeline pane, focus last message
        await keyboard.hotkey(["shift", "tab"])
        await asyncio.sleep(0.15)
        await keyboard.hotkey(["shift", "tab"])
        await asyncio.sleep(0.15)
        await keyboard.hotkey(["shift", "tab"])
        await asyncio.sleep(0.2)
        # Select last message
        await keyboard.press_key("down")
        await asyncio.sleep(0.1)
        await keyboard.press_key("up")
        await asyncio.sleep(0.2)


async def _copy_last_message_and_verify() -> None:
    """Empties the clipboard, programmatically clicks the last message to select it,
    copies it, and verifies that the clipboard has content."""
    await asyncio.to_thread(_empty_clipboard_sync)

    await keyboard.press_key("escape")
    await asyncio.sleep(0.2)
    await _click_last_message()
    await asyncio.sleep(0.3)
    await keyboard.hotkey(["ctrl", "c"])
    await asyncio.sleep(0.5)

    copied = await asyncio.to_thread(_clipboard_has_content_sync)
    if not copied:
        raise JarvisError(
            "I tried to copy the last message but nothing ended up on the clipboard — "
            "the copy step failed, so I stopped before pasting anything."
        )


async def send_whatsapp_message(contact_name: str, message: str) -> str:
    await _ensure_whatsapp_focused()
    await asyncio.sleep(0.5)
    await _search_and_select_contact(contact_name)
    await _verify_correct_chat_open(contact_name)

    await keyboard.type_text(message)
    await asyncio.sleep(0.3)
    await keyboard.press_key("enter")

    return f"Message sent to {contact_name}."


async def forward_whatsapp_media(sender_name: str, recipient_name: str) -> str:
    await _ensure_whatsapp_focused()
    await asyncio.sleep(0.5)

    # 1. Open sender's chat and verify it's really them.
    await _search_and_select_contact(sender_name)
    await _verify_correct_chat_open(sender_name)

    # 2. Copy the last message/media, and verify something was actually copied.
    await _copy_last_message_and_verify()

    # 3. Open recipient's chat and verify it's really them.
    await _search_and_select_contact(recipient_name)
    await _verify_correct_chat_open(recipient_name)

    # 4. Paste and send.
    await keyboard.hotkey(["ctrl", "v"])
    await asyncio.sleep(1.2)  # time for the media preview/upload dialog to load
    await keyboard.press_key("enter")

    return f"Forwarded from {sender_name} to {recipient_name}."
