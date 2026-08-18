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
async def test_play_music_uses_spotify_when_launch_confirmed():
    with patch("webbrowser.open", return_value=True) as mock_open, \
         patch("tools.windows.focus_window", new=AsyncMock(return_value="Switched.")), \
         patch("asyncio.sleep", new=AsyncMock()):
        result = await browser.play_music("classical piano")
    assert "Spotify" in result
    assert "spotify:" in mock_open.call_args_list[0][0][0]


@pytest.mark.asyncio
async def test_play_music_falls_back_to_youtube_when_webbrowser_open_returns_false():
    """webbrowser.open() returning False means the OS itself reported no
    handler for the URI — the old bug was that this case could never be
    detected because a try/except around a call that never raises is dead
    code. This proves the fallback fires when open() honestly reports failure."""
    with patch("webbrowser.open", return_value=False) as mock_open, \
         patch("asyncio.sleep", new=AsyncMock()):
        result = await browser.play_music("lofi beats")
    assert "YouTube" in result
    assert "youtube.com" in mock_open.call_args_list[-1][0][0]


@pytest.mark.asyncio
async def test_play_music_falls_back_to_youtube_when_spotify_window_never_appears():
    """webbrowser.open() reported success (True), but Spotify never
    actually came to the foreground — focus_window raising means it
    didn't launch, so this should still fall back honestly instead of
    claiming Spotify success on a launch call alone."""
    with patch("webbrowser.open", return_value=True) as mock_open, \
         patch("tools.windows.focus_window", new=AsyncMock(side_effect=JarvisError("not found"))), \
         patch("asyncio.sleep", new=AsyncMock()):
        result = await browser.play_music("jazz")
    assert "YouTube" in result
    assert "doesn't seem to be available" in result


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


def test_get_system_status_uses_system_drive_env_var_on_windows():
    """The fix: psutil.disk_usage("/") isn't a valid path on Windows — it
    needs an actual drive root like "C:\\". The real implementation reads
    the SystemDrive environment variable (which Windows always sets, e.g.
    "C:") rather than hardcoding a drive letter or guessing from the home
    directory — this asserts that env var is actually used when present."""
    mock_disk = MagicMock()
    mock_disk.percent = 50.0

    with patch("psutil.cpu_percent", return_value=10.0), \
         patch("psutil.virtual_memory", return_value=MagicMock(percent=20.0)), \
         patch("psutil.disk_usage", return_value=mock_disk) as mock_disk_usage, \
         patch("psutil.sensors_battery", return_value=None), \
         patch.dict("os.environ", {"SystemDrive": "D:"}):
        asyncio.run(system.get_system_status())

    called_with = mock_disk_usage.call_args[0][0]
    assert called_with == "D:\\"
    assert called_with != "/"


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

    seq_numbers = [100, 101]  # before -> after: changed, so copy is considered successful

    async def fake_seq():
        return seq_numbers.pop(0)

    with patch("tools.windows.focus_window", new=AsyncMock(return_value="Switched.")), \
         patch("tools.keyboard.hotkey", new=AsyncMock()) as mock_hotkey, \
         patch("tools.keyboard.type_text", new=AsyncMock()) as mock_type, \
         patch("tools.keyboard.press_key", new=AsyncMock()), \
         patch("tools.windows.read_window_text", new=fake_read), \
         patch.object(whatsapp, "_click_last_message", new=AsyncMock(return_value=True)), \
         patch("tools.whatsapp.get_clipboard_sequence_number", new=fake_seq), \
         patch("asyncio.sleep", new=AsyncMock()):
        result = await whatsapp.forward_whatsapp_media("Govardhan", "Mummy")

    assert "Forwarded from Govardhan to Mummy" in result
    mock_hotkey.assert_any_call(["ctrl", "c"])
    mock_hotkey.assert_any_call(["ctrl", "v"])
    mock_type.assert_any_call("Govardhan")
    mock_type.assert_any_call("Mummy")


@pytest.mark.asyncio
async def test_forward_whatsapp_media_refuses_when_clipboard_unchanged():
    """This is the exact bug that shipped and reached a real user: the
    copy step doesn't always land on something copyable, Ctrl+C copies
    nothing, and the old code pasted+sent an empty message anyway while
    claiming "Forwarded" — no message was actually sent. Verification now
    uses the clipboard SEQUENCE NUMBER (format-agnostic — catches images
    too, not just text, unlike the old GetClipboardFormats() check), and
    must refuse before ever pasting or claiming success if it never changes,
    even after the one built-in retry."""
    from tools import whatsapp

    async def fake_seq():
        return 42  # same value every call — clipboard never actually changed

    with patch("tools.windows.focus_window", new=AsyncMock(return_value="Switched.")), \
         patch("tools.keyboard.hotkey", new=AsyncMock()) as mock_hotkey, \
         patch("tools.keyboard.type_text", new=AsyncMock()), \
         patch("tools.keyboard.press_key", new=AsyncMock()), \
         patch("tools.windows.read_window_text", new=AsyncMock(return_value="Chat with Govardhan")), \
         patch.object(whatsapp, "_click_last_message", new=AsyncMock(return_value=True)), \
         patch("tools.whatsapp.get_clipboard_sequence_number", new=fake_seq), \
         patch("asyncio.sleep", new=AsyncMock()):
        with pytest.raises(JarvisError) as excinfo:
            await whatsapp.forward_whatsapp_media("Govardhan", "Mummy")

    assert "clipboard never changed" in str(excinfo.value)
    # The paste step (ctrl+v) must NEVER have been reached.
    paste_calls = [c for c in mock_hotkey.call_args_list if c.args[0] == ["ctrl", "v"]]
    assert not paste_calls


@pytest.mark.asyncio
async def test_forward_whatsapp_media_retries_clipboard_check_once_before_failing():
    """Some clipboard writes (especially image/media) populate a beat
    after the copy hotkey fires — the check must retry once before
    concluding the copy genuinely failed, not fail on the very first read."""
    from tools import whatsapp

    seq_numbers = [5, 5, 6]  # before=5, first check still 5 (not yet), retry sees 6 (changed)

    async def fake_seq():
        return seq_numbers.pop(0)

    with patch("tools.windows.focus_window", new=AsyncMock(return_value="Switched.")), \
         patch("tools.keyboard.hotkey", new=AsyncMock()), \
         patch("tools.keyboard.type_text", new=AsyncMock()), \
         patch("tools.keyboard.press_key", new=AsyncMock()), \
         patch("tools.windows.read_window_text", new=AsyncMock(side_effect=["Chat with Govardhan", "Chat with Mummy"])), \
         patch.object(whatsapp, "_click_last_message", new=AsyncMock(return_value=True)), \
         patch("tools.whatsapp.get_clipboard_sequence_number", new=fake_seq), \
         patch("asyncio.sleep", new=AsyncMock()):
        result = await whatsapp.forward_whatsapp_media("Govardhan", "Mummy")

    assert "Forwarded" in result


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
