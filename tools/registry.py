"""
Single choke point through which every tool call passes. This is what makes
the security model real: the orchestrator never calls tool functions
directly — it always goes through ToolRegistry.execute(), which validates
first.
"""
from __future__ import annotations

import time
from typing import Awaitable, Callable

from core.errors import ConfirmationRequiredError, JarvisError, ToolNotFoundError
from core.logging_setup import log
from core.memory import Memory
from core.security import SecurityGate
from tools import applications, browser, filesystem, instagram, keyboard, mouse, project_runner, system, whatsapp, windows
from vision.read_screen import read_screen

ToolFunc = Callable[..., Awaitable[str]]


class ToolRegistry:
    def __init__(self, memory: Memory) -> None:
        self._memory = memory
        self._security = SecurityGate()
        self._tools: dict[str, ToolFunc] = {
            "open_application": applications.open_application,
            "close_application": applications.close_application,
            "get_running_processes": lambda **_: applications.get_running_processes(),
            "open_url": browser.open_url,
            "web_search": browser.web_search,
            "control_volume": system.control_volume,
            "screenshot": lambda **_: system.screenshot(),
            "create_folder": filesystem.create_folder,
            "list_directory": filesystem.list_directory,
            "find_file": filesystem.find_file,
            "delete_path": filesystem.delete_path,
            "system_power": system.system_power,
            "remember": self._remember,
            "recall": self._recall,
            "read_screen": lambda **_: read_screen(),
            "start_project": project_runner.start_project,
            "stop_project": project_runner.stop_project,
            "list_open_windows": lambda **_: windows.list_open_windows(),
            "get_active_window": lambda **_: windows.get_active_window(),
            "focus_window": windows.focus_window,
            "read_window_text": windows.read_window_text,
            "list_browser_tabs": windows.list_browser_tabs,
            "type_text": keyboard.type_text,
            "press_key": keyboard.press_key,
            "hotkey": keyboard.hotkey,
            "move_mouse": mouse.move_mouse,
            "click": mouse.click,
            "click_control": mouse.click_control,
            "send_whatsapp_message": whatsapp.send_whatsapp_message,
            "forward_whatsapp_media": whatsapp.forward_whatsapp_media,
            "open_whatsapp_chat": whatsapp.open_whatsapp_chat,
            "send_instagram_message": instagram.send_instagram_message,
            "send_instagram_reel": instagram.send_instagram_reel,
            "open_website_or_search": browser.open_website_or_search,
            "control_browser_tabs": browser.control_browser_tabs,
            "play_music": browser.play_music,
            "quick_note": filesystem.quick_note,
            "create_file": filesystem.create_file,
            "open_system_folder": filesystem.open_system_folder,
            "find_and_open_file": filesystem.find_and_open_file,
            "media_control": system.media_control,
            "window_action": system.window_action,
            "get_system_status": lambda **_: system.get_system_status(),
            "calculate": system.calculate,
        }

    async def _remember(self, key: str, value: str) -> str:
        await self._memory.set(key, value)
        return f"Got it, I'll remember {key}."

    async def _recall(self, key: str | None = None) -> str:
        if key:
            value = await self._memory.get(key)
            return value if value else f"I don't have anything saved for {key}."
        all_mem = await self._memory.get_all()
        if not all_mem:
            return "I don't have any memories saved yet."
        return "; ".join(f"{k}: {v}" for k, v in all_mem.items())

    @property
    def security(self) -> SecurityGate:
        return self._security

    async def execute(self, tool_name: str, args: dict, *, skip_confirmation_check: bool = False) -> str:
        """Validate + run a tool. Raises ConfirmationRequiredError for
        dangerous tools unless skip_confirmation_check=True (used when the
        orchestrator is re-running an already-confirmed action)."""
        func = self._tools.get(tool_name)
        if func is None:
            raise ToolNotFoundError(f"I don't have a way to do that yet.")

        if not skip_confirmation_check:
            self._security.check(tool_name, args)  # may raise ConfirmationRequiredError

        start = time.monotonic()
        try:
            result = await func(**args)
        except JarvisError:
            raise
        except TypeError as exc:
            raise JarvisError("I got that command wrong internally.", technical_detail=str(exc))
        elapsed_ms = (time.monotonic() - start) * 1000
        log.info("Tool '%s' completed in %.0fms", tool_name, elapsed_ms)
        return result
