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
from tools import applications, browser, filesystem, system

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
