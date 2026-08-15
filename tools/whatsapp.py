"""
Automated WhatsApp macro. Bypasses the slow UIA tree-walk queries and
instead uses fast native keyboard hotkeys (Ctrl+F to search, typing the
contact, selecting, typing the message, and sending). This reduces the
entire interaction to a single fast tool call, making it run in 3-4 seconds.
"""
from __future__ import annotations

import asyncio
from tools import applications, keyboard, windows
from core.errors import JarvisError


async def send_whatsapp_message(contact_name: str, message: str) -> str:
    # 1. Focus WhatsApp window (open it first if not running)
    try:
        await windows.focus_window("WhatsApp")
    except Exception:
        await applications.open_application("WhatsApp")
        # Give the app a moment to launch and render
        await asyncio.sleep(2.5)
        try:
            await windows.focus_window("WhatsApp")
        except Exception as exc:
            raise JarvisError("I opened WhatsApp, but couldn't focus the window.", technical_detail=str(exc))

    await asyncio.sleep(0.5)

    # 2. Press Ctrl+F to focus the contact search bar
    await keyboard.hotkey(["ctrl", "f"])
    await asyncio.sleep(0.3)
    await keyboard.hotkey(["ctrl", "a"])
    await asyncio.sleep(0.1)
    await keyboard.press_key("backspace")
    await asyncio.sleep(0.1)

    # 3. Type the contact name
    await keyboard.type_text(contact_name)
    # Give search results a moment to filter
    await asyncio.sleep(1.0)

    # 4. Press Enter to select the contact and focus the message input field
    await keyboard.press_key("enter")
    await asyncio.sleep(0.5)

    # 5. Type the message
    await keyboard.type_text(message)
    await asyncio.sleep(0.3)

    # 6. Press Enter to send
    await keyboard.press_key("enter")

    return f"Message successfully sent to {contact_name}."


async def forward_whatsapp_media(sender_name: str, recipient_name: str) -> str:
    # 1. Focus WhatsApp window (open it first if not running)
    try:
        await windows.focus_window("WhatsApp")
    except Exception:
        await applications.open_application("WhatsApp")
        await asyncio.sleep(2.5)
        try:
            await windows.focus_window("WhatsApp")
        except Exception as exc:
            raise JarvisError("I opened WhatsApp, but couldn't focus the window.", technical_detail=str(exc))

    await asyncio.sleep(0.5)

    # 2. Open sender's chat
    await keyboard.hotkey(["ctrl", "f"])
    await asyncio.sleep(0.3)
    await keyboard.hotkey(["ctrl", "a"])
    await asyncio.sleep(0.1)
    await keyboard.press_key("backspace")
    await asyncio.sleep(0.1)
    await keyboard.type_text(sender_name)
    await asyncio.sleep(1.0)
    await keyboard.press_key("enter")
    await asyncio.sleep(0.8)

    # 3. Focus the timeline pane and copy the last message (photo/media)
    # Shift+F6 is the standard Windows pane-cycling hotkey to jump focus from input box directly to chat timeline.
    await keyboard.press_key("escape")
    await asyncio.sleep(0.2)
    await keyboard.hotkey(["shift", "f6"])
    await asyncio.sleep(0.4)
    await keyboard.hotkey(["ctrl", "c"])
    await asyncio.sleep(0.5)

    # 4. Open recipient's chat
    await keyboard.hotkey(["ctrl", "f"])
    await asyncio.sleep(0.3)
    await keyboard.hotkey(["ctrl", "a"])
    await asyncio.sleep(0.1)
    await keyboard.press_key("backspace")
    await asyncio.sleep(0.1)
    await keyboard.type_text(recipient_name)
    await asyncio.sleep(1.0)
    await keyboard.press_key("enter")
    await asyncio.sleep(0.8)

    # 5. Paste and send the photo/media
    await keyboard.hotkey(["ctrl", "v"])
    await asyncio.sleep(1.2)  # Give time for the media preview/upload dialog to load
    await keyboard.press_key("enter")

    return f"Successfully forwarded media from {sender_name} to {recipient_name}."
