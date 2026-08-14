"""
System-level tools: volume via Windows Core Audio (pycaw), screenshots via
mss, and power actions (dangerous, gated by core/security.py already by the
time these functions run).
"""
from __future__ import annotations

import asyncio
import subprocess
from datetime import datetime
from pathlib import Path

from core.errors import JarvisError

SCREENSHOT_DIR = Path("data/screenshots")


def _get_volume_interface():
    from ctypes import cast, POINTER
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

    devices = AudioUtilities.GetSpeakers()
    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    return cast(interface, POINTER(IAudioEndpointVolume))


async def control_volume(action: str, level: int | None = None) -> str:
    def _do():
        vol = _get_volume_interface()
        if action == "mute":
            vol.SetMute(1, None)
        elif action == "unmute":
            vol.SetMute(0, None)
        elif action == "set":
            if level is None:
                raise JarvisError("I need a volume level to set.")
            vol.SetMasterVolumeLevelScalar(level / 100.0, None)
        else:
            raise JarvisError(f"Unknown volume action: {action}")

    try:
        await asyncio.to_thread(_do)
    except JarvisError:
        raise
    except Exception as exc:
        raise JarvisError("I couldn't change the volume.", technical_detail=str(exc))

    if action == "set":
        return f"Volume set to {level} percent."
    return f"Volume {action}d."


async def screenshot() -> str:
    def _do() -> str:
        import mss

        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        filename = SCREENSHOT_DIR / f"screenshot_{datetime.now():%Y%m%d_%H%M%S}.png"
        with mss.mss() as sct:
            sct.shot(output=str(filename))
        return str(filename)

    try:
        path = await asyncio.to_thread(_do)
    except Exception as exc:
        raise JarvisError("I couldn't take a screenshot.", technical_detail=str(exc))
    return f"Screenshot saved to {path}."


async def system_power(action: str) -> str:
    """Only ever reached after explicit user confirmation via core/security.py."""
    commands = {
        "shutdown": ["shutdown", "/s", "/t", "5"],
        "restart": ["shutdown", "/r", "/t", "5"],
        "sleep": ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"],
        "lock": ["rundll32.exe", "user32.dll,LockWorkStation"],
    }
    cmd = commands.get(action)
    if not cmd:
        raise JarvisError(f"I don't know how to {action} the computer.")
    try:
        await asyncio.to_thread(subprocess.run, cmd, timeout=10, check=True)
    except Exception as exc:
        raise JarvisError(f"I couldn't {action} the computer.", technical_detail=str(exc))
    return f"{action.capitalize()}ing now."
