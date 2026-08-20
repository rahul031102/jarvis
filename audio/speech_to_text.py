"""
Voice capture + transcription.

- webrtcvad detects speech vs silence per 30ms frame in real time — this is
  what lets us auto-stop recording when the user finishes talking, with no
  "press enter" step.
- faster-whisper (CTranslate2) does local transcription, loaded ONCE at
  startup and reused for every command (no repeated model init — a stated
  performance requirement).
- The provider is abstracted so a streaming cloud API (Deepgram, etc.) can
  be swapped in later without touching the orchestrator.
"""
from __future__ import annotations

import asyncio
import collections

import numpy as np
import webrtcvad

from config.settings import settings
from core.errors import JarvisError
from core.logging_setup import log

from audio.microphone import ContinuousMicrophone

SAMPLE_RATE = 16000
FRAME_MS = 30
FRAME_SAMPLES = int(SAMPLE_RATE * FRAME_MS / 1000)
SILENCE_FRAMES_TO_STOP = 25  # ~750ms of silence ends the utterance
MAX_RECORD_SECONDS = 15


class SpeechToText:
    def __init__(self, mic: ContinuousMicrophone) -> None:
        self._vad = webrtcvad.Vad(2)  # aggressiveness 2 (good balance of speech sensitivity and noise filtering)
        self._model = None  # lazy-loaded once, reused forever
        self.mic = mic

    def _ensure_model(self):
        if self._model is None:
            from faster_whisper import WhisperModel

            log.info("Loading speech recognition model (one-time)...")
            self._model = WhisperModel(settings.stt_model_size, device="auto", compute_type="auto")
        return self._model

    async def record_and_transcribe(self, max_wait_seconds: float = 15.0) -> str:
        self.mic.clear()  # Clear any stale audio before recording starts
        audio = await asyncio.to_thread(self._record_until_silence, max_wait_seconds)
        if audio is None or len(audio) == 0:
            raise JarvisError("I didn't catch that.")
        text = await asyncio.to_thread(self._transcribe, audio)
        if not text.strip():
            raise JarvisError("I didn't catch that.")
        return text.strip()

    def _record_until_silence(self, max_wait_seconds: float = 15.0) -> np.ndarray | None:
        frames: list[np.ndarray] = []
        ring_buffer: collections.deque = collections.deque(maxlen=SILENCE_FRAMES_TO_STOP)
        triggered = False
        max_frames = int(max_wait_seconds * 1000 / FRAME_MS)
        
        # Give it up to 10 seconds to start speaking for follow-ups (or min of max_wait_seconds)
        initial_wait_frames = int(min(max_wait_seconds, 10.0) * 1000 / FRAME_MS)

        trigger_window = 6
        trigger_threshold = 4
        recent_blocks = collections.deque(maxlen=trigger_window)
        recent_speech = collections.deque(maxlen=trigger_window)

        for idx in range(max_frames):
            # Read from shared microphone instead of sounddevice stream
            block = self.mic.read_samples(FRAME_SAMPLES)
            pcm = block.tobytes()
            is_speech = self._vad.is_speech(pcm, SAMPLE_RATE)

            if not triggered:
                recent_blocks.append(block)
                recent_speech.append(is_speech)
                if sum(recent_speech) >= trigger_threshold:
                    triggered = True
                    frames.extend(recent_blocks)
                elif idx > initial_wait_frames:
                    # Silently stop recording if no speech is detected within initial window
                    break
                continue

            frames.append(block)
            ring_buffer.append(is_speech)
            if len(ring_buffer) == ring_buffer.maxlen and not any(ring_buffer):
                if len(frames) >= 40:  # Minimum 1.2 seconds of recording to prevent early cut-offs on wake-cue beep
                    break

        if not frames:
            return None
        return np.concatenate(frames).astype(np.float32) / 32768.0


    def _transcribe(self, audio: np.ndarray) -> str:
        model = self._ensure_model()
        segments, _ = model.transcribe(
            audio,
            language="en",
            vad_filter=True,
            vad_parameters=dict(min_speech_duration_ms=250),  # ignore clicks/noises under 250ms
            no_speech_threshold=0.6,                          # ignore transcription of ambient/fan hums
        )
        return " ".join(seg.text for seg in segments)
