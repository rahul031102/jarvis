"""
Exercises main.py's VoiceJarvis._one_cycle control flow with every audio
component stubbed out — proves the wake -> listen -> transcribe -> process
-> speak sequencing is correct without needing a real mic/speaker, which
this sandbox doesn't have.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from ai.brain import BrainResponse
from core.memory import Memory
from tools.registry import ToolRegistry


class StubWakeWord:
    def __init__(self):
        self.calls = 0

    async def listen_for_wake_word(self):
        self.calls += 1


class StubSTT:
    def __init__(self, text: str):
        self._text = text
        self.calls = 0

    async def record_and_transcribe(self):
        self.calls += 1
        return self._text


class StubTTS:
    def __init__(self):
        self.spoken = []
        self.stopped = False

    async def speak(self, text):
        self.spoken.append(text)

    async def stop(self):
        self.stopped = True


class StubBrain:
    def __init__(self, responses):
        self._responses = list(responses)

    async def think(self, text):
        return self._responses.pop(0)

    async def continue_with_tool_results(self, assistant_content, tool_results):
        return self._responses.pop(0)


class StubOrchestrator:
    """Mirrors Orchestrator's public surface but with a stub brain wired in."""
    def __init__(self, tmp_path, responses):
        self.memory = Memory(db_path=tmp_path / "mem.db")
        self.tools = ToolRegistry(self.memory)
        self.brain = StubBrain(responses)
        self._awaiting_confirmation = False

    # Bind the real Orchestrator's methods so the full private tool-loop
    # logic (_run_tool_loop, _execute_one_tool, etc.) runs unmodified.
    from core.orchestrator import Orchestrator as _RealOrchestrator
    handle_utterance = _RealOrchestrator.handle_utterance
    _run_tool_loop = _RealOrchestrator._run_tool_loop
    _execute_one_tool = _RealOrchestrator._execute_one_tool
    _resolve_confirmation = _RealOrchestrator._resolve_confirmation


async def run_cycle(jarvis, monkeypatch):
    import main as main_module

    async def noop():
        return None

    monkeypatch.setattr(main_module, "play_wake_cue", noop)
    monkeypatch.setattr(main_module, "play_done_cue", noop)
    await main_module.VoiceJarvis._one_cycle(jarvis)


@pytest.mark.asyncio
async def test_voice_cycle_happy_path(tmp_path, monkeypatch):
    from main import VoiceJarvis

    jarvis = VoiceJarvis.__new__(VoiceJarvis)
    jarvis.wake_word = StubWakeWord()
    jarvis.stt = StubSTT("what applications are running")
    jarvis.tts = StubTTS()
    jarvis.orchestrator = StubOrchestrator(
        tmp_path,
        responses=[BrainResponse(text="A few things are open.", tool_calls=[], raw_assistant_message=None)],
    )
    jarvis.speak = lambda text: jarvis.tts.speak(text)

    await run_cycle(jarvis, monkeypatch)

    assert jarvis.wake_word.calls == 1
    assert jarvis.stt.calls == 1
    assert "A few things are open." in jarvis.tts.spoken


@pytest.mark.asyncio
async def test_voice_cycle_stop_phrase_interrupts_tts_without_calling_brain(tmp_path, monkeypatch):
    from main import VoiceJarvis

    jarvis = VoiceJarvis.__new__(VoiceJarvis)
    jarvis.wake_word = StubWakeWord()
    jarvis.stt = StubSTT("stop")
    jarvis.tts = StubTTS()
    # No brain responses queued — if the brain got called, this would raise IndexError.
    jarvis.orchestrator = StubOrchestrator(tmp_path, responses=[])
    jarvis.speak = lambda text: jarvis.tts.speak(text)

    await run_cycle(jarvis, monkeypatch)

    assert jarvis.tts.stopped is True
    assert jarvis.tts.spoken == []  # never spoke a reply — brain loop was skipped entirely
