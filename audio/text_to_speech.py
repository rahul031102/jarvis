"""
Text-to-speech, pluggable by provider. Default is edge-tts: free, low
latency, no API key. Playback is async and cancellable — a "stop" command
can interrupt mid-sentence (core requirement).
"""
from __future__ import annotations

import asyncio
import io

from config.settings import settings
from core.logging_setup import log


class TextToSpeech:
    def __init__(self) -> None:
        self._provider = settings.tts_provider
        self._current_task: asyncio.Task | None = None

    async def speak(self, text: str) -> None:
        if not text:
            return
        await self.stop()  # interrupt any in-progress speech first
        self._current_task = asyncio.create_task(self._speak_impl(text))
        try:
            await self._current_task
        except asyncio.CancelledError:
            log.info("Speech interrupted.")

    async def stop(self) -> None:
        if self._current_task and not self._current_task.done():
            self._current_task.cancel()
            try:
                await self._current_task
            except asyncio.CancelledError:
                pass
        self._current_task = None

    async def _speak_impl(self, text: str) -> None:
        if self._provider == "edge":
            await self._speak_edge(text)
        elif self._provider == "elevenlabs":
            await self._speak_elevenlabs(text)
        else:
            log.warning("Unknown TTS provider '%s', falling back to edge-tts.", self._provider)
            await self._speak_edge(text)

    async def _speak_edge(self, text: str) -> None:
        import edge_tts
        import sounddevice as sd
        import numpy as np
        from pydub import AudioSegment

        communicate = edge_tts.Communicate(text, settings.tts_voice)
        audio_bytes = bytearray()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_bytes.extend(chunk["data"])

        segment = AudioSegment.from_file(io.BytesIO(bytes(audio_bytes)), format="mp3")
        samples = np.array(segment.get_array_of_samples()).astype(np.float32) / 32768.0
        if segment.channels == 2:
            samples = samples.reshape((-1, 2))

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: sd.play(samples, samplerate=segment.frame_rate))
        await loop.run_in_executor(None, sd.wait)

    async def _speak_elevenlabs(self, text: str) -> None:
        # Pluggable slot for a paid, higher-fidelity voice. Left as an
        # explicit NotImplementedError (not a silent no-op) so it's obvious
        # this needs a real key + wiring before use, per "don't fake features".
        raise NotImplementedError(
            "ElevenLabs TTS requires ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID to be set "
            "and the elevenlabs SDK integrated — not yet wired in this build."
        )
