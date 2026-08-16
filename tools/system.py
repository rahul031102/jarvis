"""
System-level tools: volume via Windows Core Audio (pycaw), screenshots via
mss, power actions, media keys, window actions, system status, and math calculation.
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


async def media_control(action: str) -> str:
    import pyautogui
    key_map = {
        "play_pause": "playpause",
        "next_track": "nexttrack",
        "prev_track": "prevtrack",
        "mute": "volumemute",
    }
    key = key_map.get(action)
    if not key:
        raise JarvisError(f"Unknown media action: {action}")
    
    def _do():
        pyautogui.press(key)

    await asyncio.to_thread(_do)
    return f"Triggered media {action}."


async def window_action(action: str) -> str:
    import pyautogui
    def _do():
        if action == "show_desktop":
            pyautogui.hotkey("win", "d")
        elif action == "maximize":
            pyautogui.hotkey("win", "up")
        elif action == "minimize":
            pyautogui.hotkey("win", "down")
        elif action == "close":
            pyautogui.hotkey("alt", "f4")
        else:
            raise JarvisError(f"Unknown window action: {action}")

    try:
        await asyncio.to_thread(_do)
    except Exception as exc:
        raise JarvisError(f"I couldn't perform window action: {action}.", technical_detail=str(exc))
    return f"Window action {action} triggered."


async def get_system_status() -> str:
    import psutil
    def _do():
        import os

        cpu = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory().percent
        # "/" isn't a valid path on Windows — disk_usage needs a real drive
        # letter there (e.g. "C:\\"). Use the drive the OS/home dir lives on,
        # which works on both Windows and POSIX.
        system_drive = os.environ.get("SystemDrive")
        disk_path = f"{system_drive}\\" if system_drive else "/"
        disk = psutil.disk_usage(disk_path).percent
        battery = psutil.sensors_battery()
        if battery:
            bat_percent = battery.percent
            charging = "charging" if battery.power_plugged else "not charging"
            bat_status = f"{bat_percent}% ({charging})"
        else:
            bat_status = "No battery detected"
        return f"CPU: {cpu}%; RAM: {mem}%; Disk: {disk}%; Battery: {bat_status}"

    try:
        return await asyncio.to_thread(_do)
    except Exception as exc:
        raise JarvisError("I couldn't read system status.", technical_detail=str(exc))


async def calculate(expression: str) -> str:
    if not all(c in "0123456789+-*/().% " for c in expression):
        raise JarvisError("I can only calculate basic math expressions (numbers, +, -, *, /, %, parenthesis).")
    try:
        result = eval(expression, {"__builtins__": None}, {})
        return f"Result: {result}"
    except Exception as exc:
        raise JarvisError("I couldn't solve that math expression.", technical_detail=str(exc))
