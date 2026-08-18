"""
Text-to-speech, pluggable by provider. Default is edge-tts: free, low
latency, no API key. Playback is async and cancellable — a "stop" command
can interrupt mid-sentence (core requirement).

Latency note: the previous implementation buffered the ENTIRE edge-tts
response (every audio chunk) before decoding and playing anything — so a
two-sentence reply couldn't start speaking until the whole thing had
downloaded. This version pipes audio chunks into `ffplay` as they arrive
over the network, so playback starts as soon as the first chunk lands,
not after the last one. ffplay is required for this path (it's already a
hard dependency here since pydub needs ffmpeg for mp3 decoding anyway —
this doesn't add a new dependency, it uses the one already required). If
ffplay isn't found, this falls back to the old buffer-then-play behavior
rather than failing silently.
"""
from __future__ import annotations

import asyncio
import io
import shutil

from config.settings import settings
from core.logging_setup import log


class TextToSpeech:
    def __init__(self) -> None:
        self._provider = settings.tts_provider
        self._current_task: asyncio.Task | None = None
        self._ffplay_path = shutil.which("ffplay")

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
        if self._ffplay_path:
            await self._speak_edge_streaming(text)
        else:
            log.warning("ffplay not found on PATH — falling back to buffer-then-play TTS (slower). "
                        "Install ffmpeg (which provides ffplay) to fix this.")
            await self._speak_edge_buffered(text)

    async def _speak_edge_streaming(self, text: str) -> None:
        """Pipes mp3 chunks into ffplay's stdin as they stream in from
        edge-tts, instead of waiting for the full response before playing
        anything. This is the actual latency fix — perceived response time
        drops to roughly however long the first chunk takes, not the whole
        utterance's synthesis+download time."""
        import edge_tts

        proc = await asyncio.create_subprocess_exec(
            self._ffplay_path, "-nodisp", "-autoexit", "-loglevel", "quiet", "-",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        try:
            communicate = edge_tts.Communicate(text, settings.tts_voice, rate=settings.tts_rate)
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    proc.stdin.write(chunk["data"])
                    await proc.stdin.drain()
            proc.stdin.close()
            # Dynamic safety timeout to prevent ffplay from hanging indefinitely on EOF.
            # Estimated duration: ~10 chars per second + 3 seconds pad buffer.
            playback_timeout = max(4.0, len(text) / 10.0 + 3.0)
            try:
                await asyncio.wait_for(proc.wait(), timeout=playback_timeout)
            except asyncio.TimeoutError:
                log.info("ffplay playback timeout reached, terminating process...")
                proc.kill()
                await proc.wait()
        except asyncio.CancelledError:
            proc.kill()
            await proc.wait()
            raise
        except Exception:
            if proc.returncode is None:
                proc.kill()
                await proc.wait()
            raise

    async def _speak_edge_buffered(self, text: str) -> None:
        """Original buffer-everything-then-play path — kept as a fallback
        for machines without ffplay on PATH, so TTS still works, just
        without the streaming latency win."""
        import edge_tts
        import sounddevice as sd
        import numpy as np
        from pydub import AudioSegment

        communicate = edge_tts.Communicate(text, settings.tts_voice, rate=settings.tts_rate)
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
