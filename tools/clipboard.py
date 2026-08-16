"""
Thin wrapper around the Windows clipboard sequence counter.

We use this to verify a Ctrl+C actually grabbed something new, instead of
blindly trusting that the hotkey landed on selected content. Windows bumps
GetClipboardSequenceNumber() every time the clipboard content changes, in
any format (text, image, file list) — so comparing it before/after a copy
tells us definitively whether anything was captured, without having to
know or care what format the copied content is in.
"""
from __future__ import annotations

import asyncio


def _get_sequence_number_sync() -> int:
    import ctypes

    return ctypes.windll.user32.GetClipboardSequenceNumber()


async def get_clipboard_sequence_number() -> int:
    return await asyncio.to_thread(_get_sequence_number_sync)
