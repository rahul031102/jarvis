"""
Automated Instagram Web macro. Bypasses UIA entirely and uses browser navigation 
and native hotkeys/tab cycling to search contacts and send messages on Instagram Web.
"""
from __future__ import annotations

import asyncio
import webbrowser
from tools import keyboard, windows
from core.errors import JarvisError


async def send_instagram_message(username: str, message: str) -> str:
    # 1. Open the direct message compose dialog
    url = "https://www.instagram.com/direct/new/"
    try:
        await asyncio.to_thread(webbrowser.open, url)
    except Exception as exc:
        raise JarvisError("I couldn't open Instagram.", technical_detail=str(exc))
    
    # Wait for the browser to launch, load the page, and auto-focus the search bar
    await asyncio.sleep(4.0)

    # 2. Type the contact username
    await keyboard.type_text(username)
    await asyncio.sleep(1.5)  # Wait for search filtering results to render

    # 3. Press Tab to highlight the first match in the list, then Space to check/select it
    await keyboard.press_key("tab")
    await asyncio.sleep(0.2)
    await keyboard.press_key("space")
    await asyncio.sleep(0.5)

    # 4. Press Tab to highlight the "Chat" button, then Enter to launch the conversation thread
    await keyboard.press_key("tab")
    await asyncio.sleep(0.2)
    await keyboard.press_key("enter")
    await asyncio.sleep(2.0)  # Wait for the chat to open and focus the text box

    # 5. Type the message and send
    await keyboard.type_text(message)
    await asyncio.sleep(0.3)
    await keyboard.press_key("enter")

    return f"Successfully sent Instagram message to {username}."


async def send_instagram_reel(username: str, topic: str = "comedy") -> str:
    # 1. Open the reels section of Instagram
    url = "https://www.instagram.com/reels/"
    try:
        await asyncio.to_thread(webbrowser.open, url)
    except Exception as exc:
        raise JarvisError("I couldn't open Instagram Reels.", technical_detail=str(exc))
    
    # Wait for the browser to launch and load the reels page
    await asyncio.sleep(4.0)

    # 2. Get the reel's URL from the browser's address bar
    # Copy active tab's URL (Ctrl+L focuses address bar, Ctrl+C copies)
    from tools.whatsapp import _empty_clipboard_sync, _clipboard_has_content_sync
    await asyncio.to_thread(_empty_clipboard_sync)
    await keyboard.hotkey(["ctrl", "l"])
    await asyncio.sleep(0.3)
    await keyboard.hotkey(["ctrl", "c"])
    await asyncio.sleep(0.5)

    # Check if we copied it successfully
    copied = await asyncio.to_thread(_clipboard_has_content_sync)
    if not copied:
        raise JarvisError("I couldn't copy the reel link from your browser.")

    # 3. Open the Direct Message compose dialog
    dm_url = "https://www.instagram.com/direct/new/"
    await asyncio.to_thread(webbrowser.open, dm_url)
    await asyncio.sleep(3.5)

    # 4. Type the recipient's username and search
    await keyboard.type_text(username)
    await asyncio.sleep(1.5)

    # 5. Select the contact
    await keyboard.press_key("tab")
    await asyncio.sleep(0.2)
    await keyboard.press_key("space")
    await asyncio.sleep(0.5)

    # 6. Click Chat/Next
    await keyboard.press_key("tab")
    await asyncio.sleep(0.2)
    await keyboard.press_key("enter")
    await asyncio.sleep(2.0)

    # 7. Paste the copied reel link (Ctrl+V) and press Enter to send
    await keyboard.hotkey(["ctrl", "v"])
    await asyncio.sleep(0.5)
    await keyboard.press_key("enter")

    return f"Successfully sent the Instagram reel directly to {username}."
