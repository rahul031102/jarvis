"""
Everything the LLM asks for passes through here before it touches the real
system. Two jobs:

1. Validate arguments against a strict allowlist per tool (not just the JSON
   schema — the schema only checks types, this checks actual safe values).
2. Gate dangerous tools behind an explicit confirmation round-trip.

The orchestrator calls `SecurityGate.check()` before every tool execution.
If it raises ConfirmationRequiredError, the orchestrator must speak the
message and wait for the user's next utterance to be "yes"/"confirm" before
calling `SecurityGate.confirm_and_check()`.
"""
from __future__ import annotations

import re
from pathlib import Path

from ai.schemas import DANGEROUS_TOOLS
from core.errors import ConfirmationRequiredError, ToolValidationError

# Absolute paths JARVIS will never touch, even with confirmation.
PROTECTED_PATHS = (
    Path("C:/Windows"),
    Path("C:/Program Files"),
    Path("C:/Program Files (x86)"),
    Path.home(),  # the bare home dir itself, not its contents
)

_SAFE_APP_NAME = re.compile(r"^[a-zA-Z0-9 _\-\.]{1,64}$")
_SAFE_URL = re.compile(r"^https?://[^\s]+$")


class SecurityGate:
    def __init__(self) -> None:
        self._pending: dict | None = None  # the last action awaiting confirmation

    # ---------- validation ----------

    def validate(self, tool_name: str, args: dict) -> None:
        if tool_name in ("open_application", "close_application"):
            name = args.get("app_name", "")
            if not _SAFE_APP_NAME.match(name):
                raise ToolValidationError(f"'{name}' isn't a valid application name.")

        elif tool_name == "open_url":
            url = args.get("url", "")
            if not _SAFE_URL.match(url):
                raise ToolValidationError("That doesn't look like a valid URL.")

        elif tool_name == "control_volume":
            if args.get("action") == "set":
                level = args.get("level")
                if not isinstance(level, int) or not (0 <= level <= 100):
                    raise ToolValidationError("Volume level must be between 0 and 100.")

        elif tool_name in ("delete_path", "create_folder", "list_directory", "find_file"):
            path_str = args.get("path") or args.get("location") or ""
            self._validate_path_not_protected(path_str, tool_name)

    def _validate_path_not_protected(self, path_str: str, tool_name: str) -> None:
        if not path_str:
            return
        try:
            resolved = Path(path_str).expanduser().resolve()
        except Exception:
            raise ToolValidationError("That path isn't valid.")
        for protected in PROTECTED_PATHS:
            try:
                protected_resolved = protected.resolve()
            except Exception:
                continue
            if resolved == protected_resolved or (
                tool_name == "delete_path" and protected_resolved in resolved.parents
            ):
                raise ToolValidationError(
                    "That's a protected system location — I won't touch it."
                )

    # ---------- confirmation gate ----------

    def check(self, tool_name: str, args: dict) -> None:
        """Raises ConfirmationRequiredError for dangerous tools until confirmed."""
        self.validate(tool_name, args)

        if tool_name in DANGEROUS_TOOLS:
            message = self._confirmation_prompt(tool_name, args)
            self._pending = {"tool_name": tool_name, "args": args}
            raise ConfirmationRequiredError(message, pending_action=self._pending)

    def confirm_and_check(self, user_said_yes: bool) -> dict | None:
        """Call after the user responds to a pending confirmation prompt.
        Returns the approved action dict if confirmed, None if declined."""
        pending = self._pending
        self._pending = None
        if pending and user_said_yes:
            return pending
        return None

    @property
    def has_pending_confirmation(self) -> bool:
        return self._pending is not None

    @staticmethod
    def _confirmation_prompt(tool_name: str, args: dict) -> str:
        if tool_name == "delete_path":
            return f"This will permanently delete {args.get('path')}. Do you want me to continue?"
        if tool_name == "system_power":
            action = args.get("action")
            return f"This will {action} your computer. Do you want me to continue?"
        return "This action can't be undone. Do you want me to continue?"
