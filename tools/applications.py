"""
Open/close applications and query running processes.

Strategy:
- Known common apps map to their real executable / AppUserModelID so we
  launch them properly (not by guessing a Start Menu search).
- Unknown names fall back to `os.startfile`, which uses Windows' own
  file-association/registry resolution — more reliable than scripting the
  Start Menu UI.
- Closing uses psutil to find matching processes and terminate them
  gracefully (SIGTERM equivalent) before force-killing.
"""
from __future__ import annotations

import asyncio
import os
import subprocess

import psutil

from core.errors import JarvisError

# common_name -> (executable to launch, list of process names to match when closing)
KNOWN_APPS: dict[str, dict] = {
    "chrome": {"launch": "chrome", "process_names": ["chrome.exe"]},
    "notepad": {"launch": "notepad", "process_names": ["notepad.exe"]},
    "vscode": {"launch": "code", "process_names": ["Code.exe"]},
    "vs code": {"launch": "code", "process_names": ["Code.exe"]},
    "explorer": {"launch": "explorer", "process_names": ["explorer.exe"]},
    "spotify": {"launch": "spotify", "process_names": ["Spotify.exe"]},
    "calculator": {"launch": "calc", "process_names": ["CalculatorApp.exe", "calc.exe"]},
    "edge": {"launch": "msedge", "process_names": ["msedge.exe"]},
    "word": {"launch": "winword", "process_names": ["WINWORD.EXE"]},
    "excel": {"launch": "excel", "process_names": ["EXCEL.EXE"]},
    "terminal": {"launch": "wt", "process_names": ["WindowsTerminal.exe"]},
    "whatsapp": {"launch": "start whatsapp:", "process_names": ["WhatsApp.exe", "WhatsApp2.exe"]},
    "instagram": {"launch": "explorer.exe shell:AppsFolder\\Facebook.InstagramBeta_8xx8rvfyw5nnt!App", "process_names": ["Instagram.exe"]},
}


async def open_application(app_name: str) -> str:
    key = app_name.strip().lower()
    entry = KNOWN_APPS.get(key)
    launch_target = entry["launch"] if entry else app_name

    try:
        # Run in a thread — subprocess/startfile calls can briefly block.
        await asyncio.to_thread(_launch, launch_target)
    except FileNotFoundError:
        raise JarvisError(f"I couldn't find {app_name} on this computer.")
    except Exception as exc:  # pragma: no cover - defensive
        raise JarvisError(
            f"I ran into a problem opening {app_name}.",
            technical_detail=str(exc),
        )
    return f"Opening {app_name}."


def _launch(target: str) -> None:
    try:
        subprocess.Popen(target, shell=True)
    except Exception:
        os.startfile(target)  # type: ignore[attr-defined]


async def close_application(app_name: str) -> str:
    key = app_name.strip().lower()
    entry = KNOWN_APPS.get(key)
    process_names = entry["process_names"] if entry else [f"{app_name}.exe"]

    closed_any = False
    for proc in psutil.process_iter(attrs=["name"]):
        try:
            if proc.info["name"] and proc.info["name"].lower() in (p.lower() for p in process_names):
                proc.terminate()
                closed_any = True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    if not closed_any:
        raise JarvisError(f"{app_name} doesn't appear to be running.")

    # Give terminated processes a moment, then force-kill stragglers.
    await asyncio.sleep(1.5)
    for proc in psutil.process_iter(attrs=["name"]):
        try:
            if proc.info["name"] and proc.info["name"].lower() in (p.lower() for p in process_names):
                proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return f"Closed {app_name}."


async def get_running_processes() -> str:
    names = sorted({p.info["name"] for p in psutil.process_iter(attrs=["name"]) if p.info["name"]})
    # Filter to a readable subset — full process list is mostly noise.
    interesting = [n for n in names if not n.lower().startswith(("svchost", "system", "registry"))]
    return ", ".join(interesting[:40])
