"""
File and folder operations. All paths are resolved through a small set of
named locations (desktop, documents, downloads) to avoid the LLM ever
needing to know real filesystem structure, plus arbitrary absolute paths
which are checked by core/security.py before we ever get here.
"""
from __future__ import annotations

import asyncio
import shutil
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
