# PyInstaller spec for JARVIS.
#
# Build with:  pyinstaller build.spec
# Output:      dist/JARVIS/JARVIS.exe  (or dist/JARVIS.exe with onefile, see below)
#
# console=False is the whole point of this file — that's what stops a
# terminal window from ever appearing when the user double-clicks the exe.
import sys
from pathlib import Path

block_cipher = None
ROOT = Path(SPECPATH)

a = Analysis(
    ["tray_app.py"],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / "config"), "config"),
        (str(ROOT / ".env.example"), "."),
    ],
    hiddenimports=[
        "pystray._win32",
        "PIL._tkinter_finder",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="JARVIS",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,       # <- no terminal window, ever
    icon=str(ROOT / "assets" / "jarvis.ico") if (ROOT / "assets" / "jarvis.ico").exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name="JARVIS",
)
