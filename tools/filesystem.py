"""
File and folder operations. All paths are resolved through a small set of
named locations (desktop, documents, downloads) to avoid the LLM ever
needing to know real filesystem structure, plus arbitrary absolute paths
which are checked by core/security.py before we ever get here.
"""
from __future__ import annotations

import asyncio
import os
import shutil
from datetime import datetime
from pathlib import Path

from core.errors import JarvisError

NAMED_LOCATIONS = {
    "desktop": Path.home() / "Desktop",
    "documents": Path.home() / "Documents",
    "downloads": Path.home() / "Downloads",
}


def resolve_location(location: str) -> Path:
    key = location.strip().lower()
    if key in NAMED_LOCATIONS:
        return NAMED_LOCATIONS[key]
    return Path(location).expanduser()


async def create_folder(name: str, location: str) -> str:
    base = resolve_location(location)
    target = base / name
    try:
        await asyncio.to_thread(target.mkdir, parents=True, exist_ok=True)
    except Exception as exc:
        raise JarvisError(f"I couldn't create that folder.", technical_detail=str(exc))
    return f"Created folder {name} in {location}."


async def list_directory(location: str) -> str:
    base = resolve_location(location)
    if not base.exists():
        raise JarvisError(f"I couldn't find that location.")
    entries = await asyncio.to_thread(lambda: sorted(p.name for p in base.iterdir()))
    if not entries:
        return f"{location} is empty."
    return ", ".join(entries[:50])


async def find_file(pattern: str, location: str) -> str:
    base = resolve_location(location)
    if not base.exists():
        raise JarvisError("I couldn't find that location.")
    matches = await asyncio.to_thread(lambda: sorted(base.rglob(f"*{pattern}*")))
    if not matches:
        return f"No files matching '{pattern}' found in {location}."
    # Most recently modified first, top 5
    matches_with_mtime = [(m, m.stat().st_mtime) for m in matches if m.is_file()]
    matches_with_mtime.sort(key=lambda x: x[1], reverse=True)
    top = [str(m) for m, _ in matches_with_mtime[:5]]
    return "; ".join(top)


async def delete_path(path: str) -> str:
    """Only ever reached after explicit user confirmation via core/security.py."""
    target = Path(path).expanduser()
    if not target.exists():
        raise JarvisError("That path doesn't exist.")
    try:
        if target.is_dir():
            await asyncio.to_thread(shutil.rmtree, target)
        else:
            await asyncio.to_thread(target.unlink)
    except Exception as exc:
        raise JarvisError("I couldn't delete that.", technical_detail=str(exc))
    return f"Deleted {path}."


async def quick_note(text: str) -> str:
    desktop = NAMED_LOCATIONS["desktop"]
    notes_file = desktop / "notes.txt"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    def _do():
        with open(notes_file, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {text}\n")
    try:
        await asyncio.to_thread(_do)
    except Exception as exc:
        raise JarvisError("I couldn't write the note.", technical_detail=str(exc))
    return "Note saved to Desktop/notes.txt."


async def create_file(path: str, content: str) -> str:
    target = Path(path).expanduser().resolve()
    if target.exists():
        raise JarvisError(
            f"{target.name} already exists — I won't overwrite it. "
            "Delete it first or choose a different name if you want to replace it."
        )

    def _do():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    try:
        await asyncio.to_thread(_do)
    except Exception as exc:
        raise JarvisError(f"I couldn't create the file {target.name}.", technical_detail=str(exc))
    return f"Created file {target.name}."


async def open_system_folder(folder_name: str) -> str:
    folder_key = folder_name.strip().lower()
    folders = {
        "desktop": Path.home() / "Desktop",
        "documents": Path.home() / "Documents",
        "downloads": Path.home() / "Downloads",
        "pictures": Path.home() / "Pictures",
        "music": Path.home() / "Music",
        "videos": Path.home() / "Videos",
    }
    target = folders.get(folder_key)
    if target is None:
        target = Path(folder_name).expanduser().resolve()
        if not target.is_dir():
            raise JarvisError(f"'{folder_name}' isn't a valid system folder.")
    
    try:
        await asyncio.to_thread(os.startfile, str(target))
    except Exception as exc:
        raise JarvisError(f"I couldn't open {folder_name}.", technical_detail=str(exc))
    return f"Opened {folder_name}."


async def find_and_open_file(filename: str) -> str:
    search_dirs = [
        NAMED_LOCATIONS["desktop"],
        NAMED_LOCATIONS["documents"],
        NAMED_LOCATIONS["downloads"]
    ]
    matches = []
    def _search():
        for d in search_dirs:
            if d.exists():
                for p in d.rglob(f"*{filename}*"):
                    if p.is_file():
                        matches.append(p)
    await asyncio.to_thread(_search)
    if not matches:
        raise JarvisError(f"I couldn't find a file matching '{filename}'.")

    # Most recently modified first — not the raw rglob() order, which is
    # arbitrary filesystem-traversal order and can surface an old/stale
    # file ahead of the one the person actually means. Matches find_file's
    # existing recency behavior for consistency.
    matches_with_mtime = [(p, p.stat().st_mtime) for p in matches]
    matches_with_mtime.sort(key=lambda x: x[1], reverse=True)
    best_match = matches_with_mtime[0][0]

    try:
        await asyncio.to_thread(os.startfile, str(best_match))
    except Exception as exc:
        raise JarvisError(f"I found {best_match.name} but couldn't open it.", technical_detail=str(exc))
    return f"Opened {best_match.name}."
