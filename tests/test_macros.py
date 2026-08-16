"""
Tests for all the A to Z high-level desktop macro tools.
"""
import sys
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from core.errors import JarvisError
from tools import browser, filesystem, system


# --- Filesystem Macros ---

@pytest.mark.asyncio
async def test_quick_note():
    mock_open = MagicMock()
    with patch("builtins.open", mock_open):
        result = await filesystem.quick_note("hello note")
    assert "notes.txt" in result
    mock_open.assert_called_once()


@pytest.mark.asyncio
async def test_create_file():
    mock_mkdir = MagicMock()
    mock_write = MagicMock()
    with patch.object(Path, "exists", return_value=False), \
         patch.object(Path, "mkdir", mock_mkdir), patch.object(Path, "write_text", mock_write):
        result = await filesystem.create_file("C:/some/file.txt", "content here")
    assert "file.txt" in result
    mock_mkdir.assert_called_once()
    mock_write.assert_called_once_with("content here", encoding="utf-8")


@pytest.mark.asyncio
async def test_create_file_refuses_to_overwrite_existing_file():
    """The fix: create_file used to silently overwrite anything at the
    target path with zero warning — a real data-loss risk. It should now
    refuse instead."""
    mock_write = MagicMock()
    with patch.object(Path, "exists", return_value=True), \
         patch.object(Path, "write_text", mock_write):
        with pytest.raises(JarvisError) as excinfo:
            await filesystem.create_file("C:/some/existing.txt", "new content")

    assert "already exists" in str(excinfo.value)
    mock_write.assert_not_called()  # must never have touched the existing file


@pytest.mark.asyncio
async def test_open_system_folder():
    mock_start = MagicMock()
    with patch("os.startfile", mock_start):
        result = await filesystem.open_system_folder("desktop")
    assert "desktop" in result.lower()
    mock_start.assert_called_once()


@pytest.mark.asyncio
async def test_find_and_open_file():
    mock_start = MagicMock()
    # Mocking rglob to return a file
    mock_file = MagicMock(spec=Path)
    mock_file.is_file.return_value = True
    mock_file.name = "matching_doc.pdf"
    
    with patch("os.startfile", mock_start), patch.object(Path, "exists", return_value=True), patch.object(Path, "rglob", return_value=[mock_file]):
        result = await filesystem.find_and_open_file("matching_doc")
    assert "matching_doc.pdf" in result
    mock_start.assert_called_once()


# --- Browser Macros ---

@pytest.mark.asyncio
async def test_open_website_or_search_url():
    mock_open = MagicMock()
    with patch("webbrowser.open", mock_open):
        result = await browser.open_website_or_search("github.com")
    assert "github.com" in result
    mock_open.assert_called_once_with("https://github.com")


@pytest.mark.asyncio
async def test_open_website_or_search_query():
    mock_open = MagicMock()
    with patch("webbrowser.open", mock_open):
        result = await browser.open_website_or_search("how to bake bread")
    assert "Searching for" in result
    mock_open.assert_called_once()
    assert "google.com/search?q=" in mock_open.call_args[0][0]


@pytest.mark.asyncio
async def test_control_browser_tabs_basic():
    mock_hotkey = AsyncMock()
    with patch("tools.keyboard.hotkey", mock_hotkey), \
         patch("tools.windows.get_active_window", new=AsyncMock(return_value="Google Chrome")):
        res1 = await browser.control_browser_tabs("new_tab")
        res2 = await browser.control_browser_tabs("close_tab")
    assert "new" in res1
    assert "Closed" in res2
    mock_hotkey.assert_any_call(["ctrl", "t"])
    mock_hotkey.assert_any_call(["ctrl", "w"])


@pytest.mark.asyncio
async def test_control_browser_tabs_refuses_when_no_browser_focused():
    """The fix: previously new_tab/close_tab/next_tab/prev_tab sent hotkeys
    blind, regardless of what had focus. Now they check first — if no
    browser can be found or focused, refuse rather than sending Ctrl+W to
    whatever app happens to be active."""
    with patch("tools.windows.get_active_window", new=AsyncMock(return_value="Notepad")), \
         patch("tools.windows.focus_window", new=AsyncMock(side_effect=JarvisError("not found"))):
        with pytest.raises(JarvisError):
            await browser.control_browser_tabs("close_tab")


@pytest.mark.asyncio
async def test_play_music_uses_spotify_when_already_running():
    mock_open = MagicMock()
    with patch("webbrowser.open", mock_open), \
         patch("psutil.process_iter", return_value=[MagicMock(info={"name": "Spotify.exe"})]):
        result = await browser.play_music("classical piano")
    assert "Spotify" in result
    mock_open.assert_called_once()
    assert "spotify:" in mock_open.call_args[0][0]


@pytest.mark.asyncio
async def test_play_music_launches_spotify_when_installed_but_not_running():
    """Spotify wasn't running before the call, but IS running by the time
    we check again after firing the URI — simulates it launching
    successfully via the protocol handler."""
    call_count = {"n": 0}

    def fake_process_iter(attrs=None):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return []  # not running yet, before the URI is fired
        return [MagicMock(info={"name": "Spotify.exe"})]  # running now

    mock_open = MagicMock()
    with patch("webbrowser.open", mock_open), \
         patch("psutil.process_iter", side_effect=fake_process_iter), \
         patch("asyncio.sleep", new=AsyncMock()):
        result = await browser.play_music("jazz")

    assert "Spotify" in result
    mock_open.assert_called_once()  # never fell back to YouTube


@pytest.mark.asyncio
async def test_play_music_falls_back_to_youtube_when_spotify_unavailable():
    """Spotify never shows up as running, before or after — proves the
    fallback actually fires and the result is honest about what happened
    (the old bug: webbrowser.open() never raises for a missing protocol
    handler, so the except-based fallback could never trigger and would
    falsely claim Spotify success)."""
    mock_open = MagicMock()
    with patch("webbrowser.open", mock_open), \
         patch("psutil.process_iter", return_value=[]), \
         patch("asyncio.sleep", new=AsyncMock()):
        result = await browser.play_music("lofi beats")

    assert "YouTube" in result
    assert "Spotify isn't installed" in result
    assert mock_open.call_count == 2  # tried spotify: URI, then fell back
    assert "youtube.com" in mock_open.call_args[0][0]


# --- System & Window Macros ---

@pytest.mark.asyncio
async def test_media_control():
    mock_press = MagicMock()
    with patch("pyautogui.press", mock_press):
        result = await system.media_control("play_pause")
    assert "play_pause" in result
    mock_press.assert_called_once_with("playpause")


@pytest.mark.asyncio
async def test_window_action():
    mock_hotkey = MagicMock()
    with patch("pyautogui.hotkey", mock_hotkey):
        result = await system.window_action("maximize")
    assert "maximize" in result
    mock_hotkey.assert_called_once_with("win", "up")


@pytest.mark.asyncio
async def test_get_system_status():
    mock_cpu = MagicMock(return_value=12.5)
    mock_virtual = MagicMock()
    mock_virtual.percent = 45.0
    mock_disk = MagicMock()
    mock_disk.percent = 60.0
    
    with patch("psutil.cpu_percent", mock_cpu), \
         patch("psutil.virtual_memory", return_value=mock_virtual), \
         patch("psutil.disk_usage", return_value=mock_disk) as mock_disk_usage, \
         patch("psutil.sensors_battery", return_value=None):
        result = await system.get_system_status()
    
    assert "CPU: 12.5%" in result
    assert "RAM: 45.0%" in result
    assert "Disk: 60.0%" in result


def test_get_system_status_uses_valid_windows_drive_root_not_slash():
    """The fix: psutil.disk_usage("/") isn't a valid path on Windows —
    it needs an actual drive root like "C:\\". This asserts the real
    argument passed, which the mocked-return-value test above can't catch
    since it accepts any argument."""
    import os
    drive, _ = os.path.splitdrive(str(Path.home()))
    expected_root = f"{drive}\\" if drive else "C:\\"

    mock_disk = MagicMock()
    mock_disk.percent = 50.0

    with patch("psutil.cpu_percent", return_value=10.0), \
         patch("psutil.virtual_memory", return_value=MagicMock(percent=20.0)), \
         patch("psutil.disk_usage", return_value=mock_disk) as mock_disk_usage, \
         patch("psutil.sensors_battery", return_value=None):
        asyncio.run(system.get_system_status())

    called_with = mock_disk_usage.call_args[0][0]
    assert called_with != "/"
    assert called_with == expected_root


@pytest.mark.asyncio
async def test_calculate():
    res = await system.calculate("2 + 2 * 3")
    assert res == "Result: 8"

    with pytest.raises(JarvisError):
        await system.calculate("import os")


@pytest.mark.asyncio
async def test_send_whatsapp_message_succeeds_when_chat_verified():
    from tools import whatsapp

    with patch("tools.windows.focus_window", new=AsyncMock(return_value="Switched.")), \
         patch("tools.keyboard.hotkey", new=AsyncMock()), \
         patch("tools.keyboard.type_text", new=AsyncMock()), \
         patch("tools.keyboard.press_key", new=AsyncMock()), \
         patch("tools.windows.read_window_text", new=AsyncMock(return_value="Chat with Govardhan; Hey there")):
        result = await whatsapp.send_whatsapp_message("Govardhan", "On my way")

    assert "sent to Govardhan" in result


@pytest.mark.asyncio
async def test_send_whatsapp_message_refuses_when_chat_does_not_match():
    """The core safety fix: if the opened chat's visible text doesn't
    contain the contact's name, refuse to send rather than guessing —
    this is what catches "search landed on the wrong contact" before
    anything irreversible happens."""
    from tools import whatsapp

    with patch("tools.windows.focus_window", new=AsyncMock(return_value="Switched.")), \
         patch("tools.keyboard.hotkey", new=AsyncMock()), \
         patch("tools.keyboard.type_text", new=AsyncMock()) as mock_type, \
         patch("tools.keyboard.press_key", new=AsyncMock()), \
         patch("tools.windows.read_window_text", new=AsyncMock(return_value="Chat with Someone Else Entirely")):
        with pytest.raises(JarvisError) as excinfo:
            await whatsapp.send_whatsapp_message("Govardhan", "On my way")

    assert "wrong contact" in str(excinfo.value) or "doesn't show their name" in str(excinfo.value)
    # The message itself must NEVER have been typed — verification failed
    # before the send step, not after.
    mock_type.assert_called_once_with("Govardhan")


@pytest.mark.asyncio
async def test_send_whatsapp_message_refuses_when_verification_itself_fails():
    """If we genuinely can't read the chat to verify it (e.g. WhatsApp's
    accessibility tree times out), that's still not a green light to send
    — fail safe, don't fail open."""
    from tools import whatsapp

    with patch("tools.windows.focus_window", new=AsyncMock(return_value="Switched.")), \
         patch("tools.keyboard.hotkey", new=AsyncMock()), \
         patch("tools.keyboard.type_text", new=AsyncMock()) as mock_type, \
         patch("tools.keyboard.press_key", new=AsyncMock()), \
         patch("tools.windows.read_window_text", new=AsyncMock(side_effect=JarvisError("timed out"))):
        with pytest.raises(JarvisError):
            await whatsapp.send_whatsapp_message("Govardhan", "On my way")

    mock_type.assert_called_once_with("Govardhan")  # never typed the message


@pytest.mark.asyncio
async def test_forward_whatsapp_media_succeeds_when_both_chats_verified():
    from tools import whatsapp

    read_results = ["Chat with Govardhan", "Chat with Mummy"]

    async def fake_read(name):
        return read_results.pop(0)

    with patch("tools.windows.focus_window", new=AsyncMock(return_value="Switched.")), \
         patch("tools.keyboard.hotkey", new=AsyncMock()) as mock_hotkey, \
         patch("tools.keyboard.type_text", new=AsyncMock()) as mock_type, \
         patch("tools.keyboard.press_key", new=AsyncMock()), \
         patch("tools.windows.read_window_text", new=fake_read), \
         patch.object(whatsapp, "_empty_clipboard_sync", return_value=None), \
         patch.object(whatsapp, "_clipboard_has_content_sync", return_value=True):
        result = await whatsapp.forward_whatsapp_media("Govardhan", "Mummy")

    assert "Forwarded from Govardhan to Mummy" in result
    mock_hotkey.assert_any_call(["ctrl", "c"])
    mock_hotkey.assert_any_call(["ctrl", "v"])
    mock_type.assert_any_call("Govardhan")
    mock_type.assert_any_call("Mummy")


@pytest.mark.asyncio
async def test_forward_whatsapp_media_refuses_when_clipboard_stays_empty():
    """This is the exact bug that shipped and reached a real user: the
    Shift+F6 focus-jump never lands on something copyable in some cases,
    Ctrl+C copies nothing, and the old code pasted+sent an empty message
    anyway while claiming "Forwarded" — no message was actually sent.
    With clipboard verification, this must now refuse before ever pasting
    or claiming success."""
    from tools import whatsapp

    with patch("tools.windows.focus_window", new=AsyncMock(return_value="Switched.")), \
         patch("tools.keyboard.hotkey", new=AsyncMock()) as mock_hotkey, \
         patch("tools.keyboard.type_text", new=AsyncMock()), \
         patch("tools.keyboard.press_key", new=AsyncMock()), \
         patch("tools.windows.read_window_text", new=AsyncMock(return_value="Chat with Govardhan")), \
         patch.object(whatsapp, "_empty_clipboard_sync", return_value=None), \
         patch.object(whatsapp, "_clipboard_has_content_sync", return_value=False):
        with pytest.raises(JarvisError) as excinfo:
            await whatsapp.forward_whatsapp_media("Govardhan", "Mummy")

    assert "nothing ended up on the clipboard" in str(excinfo.value)
    # The paste step (ctrl+v) must NEVER have been reached.
    paste_calls = [c for c in mock_hotkey.call_args_list if c.args[0] == ["ctrl", "v"]]
    assert not paste_calls


@pytest.mark.asyncio
async def test_forward_whatsapp_media_refuses_when_sender_chat_wrong():
    from tools import whatsapp

    with patch("tools.windows.focus_window", new=AsyncMock(return_value="Switched.")), \
         patch("tools.keyboard.hotkey", new=AsyncMock()) as mock_hotkey, \
         patch("tools.keyboard.type_text", new=AsyncMock()), \
         patch("tools.keyboard.press_key", new=AsyncMock()), \
         patch("tools.windows.read_window_text", new=AsyncMock(return_value="Chat with Nobody Relevant")):
        with pytest.raises(JarvisError):
            await whatsapp.forward_whatsapp_media("Govardhan", "Mummy")

    # Must never have reached the copy step (ctrl+c) if the sender's chat
    # wasn't verified — searching itself legitimately calls hotkey first,
    # so the real assertion is that it never got to the copy.
    copy_calls = [c for c in mock_hotkey.call_args_list if c.args[0] == ["ctrl", "c"]]
    assert not copy_calls
