import sys, asyncio
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from core.memory import Memory

@pytest.mark.asyncio
async def test_memory_roundtrip(tmp_path):
    mem = Memory(db_path=tmp_path / "mem.db")
    await mem.set("main_project", "C:/Projects/JARVIS")
    val = await mem.get("main_project")
    assert val == "C:/Projects/JARVIS"

    await mem.set("main_project", "C:/Projects/JARVIS2")  # update
    val2 = await mem.get("main_project")
    assert val2 == "C:/Projects/JARVIS2"

    all_mem = await mem.get_all()
    assert "main_project" in all_mem

    deleted = await mem.delete("main_project")
    assert deleted is True
    assert await mem.get("main_project") is None
