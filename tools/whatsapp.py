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
    """Refuses to proceed if we can't confirm the opened chat actually
    belongs to the requested contact — sending to the wrong person is
    exactly the kind of mistake this check exists to catch before it's
    irreversible."""
    try:
        visible_text = await windows.read_window_text("WhatsApp")
    except JarvisError as exc:
        raise JarvisError(
            f"I couldn't confirm {contact_name}'s chat actually opened, so I stopped before sending anything. "
            f"({exc.speakable_message})"
        )
    if contact_name.strip().lower() not in visible_text.lower():
        raise JarvisError(
            f"I searched for {contact_name} but the chat that opened doesn't show their name — "
            f"it may be the wrong contact, so I stopped before sending anything."
        )


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


async def _copy_last_message_and_verify() -> None:
    """Empties the clipboard, attempts to focus the timeline and copy the
    last message, then verifies the clipboard actually received
    something new. Raises if nothing was copied — see the module
    docstring for why this check exists."""
    await asyncio.to_thread(_empty_clipboard_sync)

    await keyboard.press_key("escape")
    await asyncio.sleep(0.2)
    await keyboard.hotkey(["shift", "f6"])
    await asyncio.sleep(0.4)
    await keyboard.hotkey(["ctrl", "c"])
    await asyncio.sleep(0.5)

    copied = await asyncio.to_thread(_clipboard_has_content_sync)
    if not copied:
        raise JarvisError(
            "I tried to copy the last message but nothing ended up on the clipboard — "
            "the copy step didn't land on the right element, so I stopped before pasting anything."
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
