"""
Registers/unregisters JARVIS to launch silently at Windows login, via the
per-user registry Run key (HKCU\\...\\Run — no admin rights needed, unlike
a real Windows Service, which is the tradeoff for keeping setup simple).

Usage (after building with PyInstaller, from dist/JARVIS/):
    python autostart.py install     # add to startup
    python autostart.py uninstall   # remove from startup
    python autostart.py status      # check current state

This only does anything on Windows; it's a clear no-op elsewhere so it's
safe to import/call from anywhere without platform-checking every call site.
"""
from __future__ import annotations

import sys
from pathlib import Path

APP_NAME = "JARVIS"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def _exe_path() -> str:
    """Path to register: the built JARVIS.exe next to this script if it
    exists (packaged install), otherwise falls back to `pythonw tray_app.py`
    for a dev/source install so this is useful before you've packaged."""
    packaged = Path(__file__).resolve().parent / "JARVIS.exe"
    if packaged.exists():
        return f'"{packaged}"'
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    script = Path(__file__).resolve().parent / "tray_app.py"
    interpreter = pythonw if pythonw.exists() else Path(sys.executable)
    return f'"{interpreter}" "{script}"'


def install() -> None:
    if sys.platform != "win32":
        print("Autostart registration is Windows-only; skipping.")
        return
    import winreg

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, _exe_path())
    print(f"JARVIS registered to start at login ({_exe_path()}).")


def uninstall() -> None:
    if sys.platform != "win32":
        print("Autostart registration is Windows-only; skipping.")
        return
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, APP_NAME)
        print("JARVIS removed from startup.")
    except FileNotFoundError:
        print("JARVIS wasn't registered for startup — nothing to do.")


def status() -> None:
    if sys.platform != "win32":
        print("Autostart registration is Windows-only.")
        return
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ) as key:
            value, _ = winreg.QueryValueEx(key, APP_NAME)
        print(f"Registered: {value}")
    except FileNotFoundError:
        print("Not registered for startup.")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "install":
        install()
    elif cmd == "uninstall":
        uninstall()
    elif cmd == "status":
        status()
    else:
        print(__doc__)
        print("Usage: python autostart.py [install|uninstall|status]")
