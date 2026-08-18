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

        elif tool_name in ("delete_path", "create_folder", "list_directory", "find_file", "start_project", "stop_project"):
            path_str = args.get("path") or args.get("location") or ""
            self._validate_path_not_protected(path_str, tool_name)

        elif tool_name in ("send_whatsapp_message", "open_whatsapp_chat"):
            contact = args.get("contact_name", "")
            if not _SAFE_APP_NAME.match(contact):
                raise ToolValidationError("That doesn't look like a valid contact name.")

        elif tool_name in ("send_instagram_message", "send_instagram_reel"):
            username = args.get("username", "")
            if not _SAFE_APP_NAME.match(username):
                raise ToolValidationError("That doesn't look like a valid username.")

        elif tool_name == "forward_whatsapp_media":
            sender = args.get("sender_name", "")
            recipient = args.get("recipient_name", "")
            for contact in (sender, recipient):
                if not _SAFE_APP_NAME.match(contact):
                    raise ToolValidationError("That doesn't look like a valid contact name.")

        elif tool_name == "open_website_or_search":
            query = args.get("query", "")
            if not isinstance(query, str) or not query.strip():
                raise ToolValidationError("Query must be a non-empty string.")

        elif tool_name == "control_browser_tabs":
            action = args.get("action", "")
            if action not in ("new_tab", "close_tab", "next_tab", "prev_tab", "focus_tab"):
                raise ToolValidationError(f"Invalid tab action: {action}")
            tab_name = args.get("tab_name")
            if action == "focus_tab" and (not tab_name or not isinstance(tab_name, str)):
                raise ToolValidationError("A valid tab name must be specified to focus.")

        elif tool_name in ("create_file", "open_system_folder"):
            path_str = args.get("path") or args.get("folder_name") or ""
            self._validate_path_not_protected(path_str, tool_name)

        elif tool_name == "media_control":
            action = args.get("action", "")
            if action not in ("play_pause", "next_track", "prev_track", "mute"):
                raise ToolValidationError(f"Invalid media action: {action}")

        elif tool_name == "window_action":
            action = args.get("action", "")
            if action not in ("show_desktop", "maximize", "minimize", "close"):
                raise ToolValidationError(f"Invalid window action: {action}")

        elif tool_name in ("move_mouse", "click"):
            self._validate_coordinates(args)

        elif tool_name in ("press_key", "hotkey"):
            self._validate_keys(tool_name, args)

    def _validate_coordinates(self, args: dict) -> None:
        from tools.mouse import MAX_COORDINATE

        x, y = args.get("x"), args.get("y")
        for val in (x, y):
            if val is not None and not (isinstance(val, int) and 0 <= val <= MAX_COORDINATE):
                raise ToolValidationError("Those coordinates don't look valid.")

    def _validate_keys(self, tool_name: str, args: dict) -> None:
        from tools.keyboard import VALID_KEYS

        keys = [args["key"]] if tool_name == "press_key" else args.get("keys", [])
        if tool_name == "hotkey" and (not keys or len(keys) > 4):
            raise ToolValidationError("That doesn't look like a valid key combination.")
        for k in keys:
            if not isinstance(k, str) or k.strip().lower() not in VALID_KEYS:
                raise ToolValidationError(f"'{k}' isn't a key I recognize.")

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
