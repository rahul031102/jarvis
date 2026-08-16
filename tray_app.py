"""
System-tray shell for JARVIS.

This is the "professional" entry point: no console window, just a tray
icon with Start/Stop/Open Logs/Quit. The actual voice loop (main.py's
VoiceJarvis) is unchanged — this just hosts it.

Why a background thread + its own asyncio loop, instead of running
run_forever() directly: pystray's icon.run() blocks the main thread and
owns its own event loop expectations (especially on Windows, where the
tray icon needs to pump Win32 messages on the main thread). Trying to run
asyncio.run() on the main thread instead would block that message pump and
the tray icon would freeze/disappear. So: tray icon owns the main thread,
JARVIS's async loop runs in a dedicated worker thread with its own event
loop, and the two talk to each other only through thread-safe calls
(asyncio.run_coroutine_threadsafe / call_soon_threadsafe).

Packaging note: build this with PyInstaller in --noconsole / --windowed
mode (see build.spec) so double-clicking the .exe never opens a terminal.
"""
from __future__ import annotations

import asyncio
import sys
import threading
import webbrowser
from pathlib import Path

import pystray
from PIL import Image, ImageDraw

from config.settings import settings
from core.logging_setup import log
from main import VoiceJarvis

ROOT_DIR = Path(__file__).resolve().parent
LOG_FILE = Path(settings.log_file)


def _build_icon_image(running: bool) -> Image.Image:
    """Simple generated icon — a filled circle, green while listening,
    grey while stopped. Swap this for a real .ico/.png asset any time by
    replacing this function's body with Image.open(...)."""
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    color = (46, 204, 113, 255) if running else (127, 140, 141, 255)
    draw.ellipse((4, 4, size - 4, size - 4), fill=color)
    return img


class JarvisTrayApp:
    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._jarvis: VoiceJarvis | None = None
        self._run_task: asyncio.Task | None = None
        self._running = False

        self.icon = pystray.Icon(
            "jarvis",
            _build_icon_image(running=False),
            "JARVIS (stopped)",
            menu=self._build_menu(),
        )

    # ---- menu ----------------------------------------------------------
    def _build_menu(self) -> pystray.Menu:
        return pystray.Menu(
            pystray.MenuItem(
                "Start listening",
                self._on_start,
                enabled=lambda item: not self._running,
            ),
            pystray.MenuItem(
                "Stop",
                self._on_stop,
                enabled=lambda item: self._running,
            ),
            pystray.MenuItem("Open logs", self._on_open_logs),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit JARVIS", self._on_quit),
        )

    def _refresh_icon(self) -> None:
        self.icon.icon = _build_icon_image(self._running)
        self.icon.title = "JARVIS (listening)" if self._running else "JARVIS (stopped)"
        self.icon.update_menu()

    # ---- worker thread / event loop ------------------------------------
    def _ensure_worker_loop(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return

        ready = threading.Event()

        def _worker() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._loop = loop
            ready.set()
            try:
                loop.run_forever()
            finally:
                loop.close()

        self._thread = threading.Thread(target=_worker, name="jarvis-loop", daemon=True)
        self._thread.start()
        ready.wait(timeout=5.0)

    def _on_start(self, icon=None, item=None) -> None:
        if self._running:
            return
        self._ensure_worker_loop()
        assert self._loop is not None

        async def _run():
            self._jarvis = VoiceJarvis()
            try:
                await self._jarvis.run_forever()
            except asyncio.CancelledError:
                pass
            finally:
                if self._jarvis is not None:
                    self._jarvis.mic.close()

        def _submit():
            self._run_task = self._loop.create_task(_run())

        self._loop.call_soon_threadsafe(_submit)
        self._running = True
        self._refresh_icon()
        log.info("JARVIS started from tray.")

    def _on_stop(self, icon=None, item=None) -> None:
        if not self._running or self._loop is None:
            return

        def _cancel():
            if self._run_task is not None:
                self._run_task.cancel()

        self._loop.call_soon_threadsafe(_cancel)
        self._running = False
        self._refresh_icon()
        log.info("JARVIS stopped from tray.")

    def _on_open_logs(self, icon=None, item=None) -> None:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        LOG_FILE.touch(exist_ok=True)
        webbrowser.open(str(LOG_FILE))

    def _on_quit(self, icon=None, item=None) -> None:
        self._on_stop()
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._loop.stop)
        self.icon.stop()

    def run(self) -> None:
        # Auto-start listening as soon as the tray icon is up, so launching
        # the app IS starting JARVIS — no extra click needed on boot.
        self.icon.run(setup=lambda icon: (icon.__setattr__("visible", True), self._on_start()))


def main() -> None:
    app = JarvisTrayApp()
    app.run()


if __name__ == "__main__":
    main()
