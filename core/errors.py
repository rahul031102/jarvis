"""
Every user-facing error goes through here. The rule: JARVIS speaks a short,
useful sentence; the full exception/traceback goes only to the log file.
"""
from __future__ import annotations

import traceback

from core.logging_setup import log


class JarvisError(Exception):
    """Base class for errors that already have a safe, speakable message."""

    def __init__(self, speakable_message: str, *, technical_detail: str | None = None):
        super().__init__(speakable_message)
        self.speakable_message = speakable_message
        self.technical_detail = technical_detail


class ToolNotFoundError(JarvisError):
    pass


class ToolValidationError(JarvisError):
    pass


class ConfirmationRequiredError(JarvisError):
    """Raised when a dangerous tool is invoked without prior confirmation."""

    def __init__(self, speakable_message: str, *, pending_action: dict):
        super().__init__(speakable_message)
        self.pending_action = pending_action


def to_speakable(exc: Exception) -> str:
    """Convert any exception into something safe to say out loud, logging the
    full detail separately."""
    if isinstance(exc, JarvisError):
        if exc.technical_detail:
            log.debug("Technical detail: %s", exc.technical_detail)
        return exc.speakable_message

    log.debug("Unhandled exception:\n%s", traceback.format_exc())

    # Map common exception types to plain-English messages.
    if isinstance(exc, FileNotFoundError):
        return "I couldn't find that file or application."
    if isinstance(exc, PermissionError):
        return "I don't have permission to do that."
    if isinstance(exc, TimeoutError):
        return "That took too long and timed out."
    if isinstance(exc, ConnectionError):
        return "I'm having trouble connecting to the internet."

    return "Something went wrong on my end. I've logged the details."
