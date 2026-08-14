"""
Exercises the orchestrator's tool-call loop and the dangerous-action
confirmation round-trip WITHOUT hitting the real Anthropic API — the Brain
is replaced by a stub that returns pre-scripted responses. This proves the
control flow (ack -> execute -> confirm -> resolve) works independent of
the LLM itself.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from ai.brain import BrainResponse, ToolCallRequest
from core.memory import Memory
from core.orchestrator import Orchestrator
from tools.registry import ToolRegistry


class StubBrain:
    """Replays a scripted sequence of BrainResponses."""

    def __init__(self, script: list[BrainResponse]):
        self._script = list(script)

    async def think(self, user_text: str) -> BrainResponse:
        return self._script.pop(0)

    async def continue_with_tool_results(self, assistant_content, tool_results) -> BrainResponse:
        return self._script.pop(0)


@pytest.fixture
def spoken():
    lines: list[str] = []

    async def speak(text: str) -> None:
        lines.append(text)

    return lines, speak


@pytest.mark.asyncio
async def test_remember_tool_full_loop(tmp_path, spoken):
    lines, speak = spoken
    orch = Orchestrator.__new__(Orchestrator)  # bypass __init__ to inject stub brain
    orch.memory = Memory(db_path=tmp_path / "mem.db")
    orch.tools = ToolRegistry(orch.memory)
    orch._awaiting_confirmation = False

    call = ToolCallRequest(id="1", name="remember", input={"key": "main_project", "value": "C:/Projects/JARVIS"})
    orch.brain = StubBrain([
        BrainResponse(text=None, tool_calls=[call], raw_assistant_message={"role": "assistant"}),
        BrainResponse(text="Done.", tool_calls=[], raw_assistant_message=None),
    ])

    result = await orch.handle_utterance("remember my main project is C:/Projects/JARVIS", speak=speak)

    assert result == "Done."
    assert any("Saving that" in line for line in lines)
    stored = await orch.memory.get("main_project")
    assert stored == "C:/Projects/JARVIS"


@pytest.mark.asyncio
async def test_dangerous_tool_requires_confirmation_then_executes(tmp_path, spoken, monkeypatch):
    lines, speak = spoken
    orch = Orchestrator.__new__(Orchestrator)
    orch.memory = Memory(db_path=tmp_path / "mem.db")
    orch.tools = ToolRegistry(orch.memory)
    orch._awaiting_confirmation = False

    target_file = tmp_path / "junk.txt"
    target_file.write_text("delete me")

    call = ToolCallRequest(id="1", name="delete_path", input={"path": str(target_file)})
    orch.brain = StubBrain([
        BrainResponse(text=None, tool_calls=[call], raw_assistant_message={"role": "assistant"}),
    ])

    # Step 1: request delete -> should NOT delete, should ask for confirmation.
    result1 = await orch.handle_utterance(f"delete {target_file}", speak=speak)
    assert result1 is None or result1 == ""
    assert target_file.exists()
    assert orch._awaiting_confirmation is True
    assert any("permanently delete" in line for line in lines)

    # Step 2: user confirms -> now it should actually delete.
    result2 = await orch.handle_utterance("yes", speak=speak)
    assert not target_file.exists()
    assert "Deleted" in result2


@pytest.mark.asyncio
async def test_dangerous_tool_declined_does_not_execute(tmp_path, spoken):
    lines, speak = spoken
    orch = Orchestrator.__new__(Orchestrator)
    orch.memory = Memory(db_path=tmp_path / "mem.db")
    orch.tools = ToolRegistry(orch.memory)
    orch._awaiting_confirmation = False

    target_file = tmp_path / "keep_me.txt"
    target_file.write_text("do not delete")

    call = ToolCallRequest(id="1", name="delete_path", input={"path": str(target_file)})
    orch.brain = StubBrain([
        BrainResponse(text=None, tool_calls=[call], raw_assistant_message={"role": "assistant"}),
    ])

    await orch.handle_utterance(f"delete {target_file}", speak=speak)
    result = await orch.handle_utterance("no", speak=speak)

    assert target_file.exists()  # never deleted
    assert "won't do that" in result
