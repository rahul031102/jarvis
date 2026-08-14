"""
Offline wake-word detection using openWakeWord's pre-trained "hey jarvis"
model — no cloud calls, low CPU, runs continuously without burning API
budget or bandwidth (the stated performance requirement).

API verified against the current openWakeWord README (dscripka/openWakeWord):
  from openwakeword.model import Model
  model = Model(wakeword_models=[...])
  prediction = model.predict(frame)  # frame = 16-bit 16kHz PCM, ideally 80ms chunks

We use the built-in "hey_jarvis" model rather than a custom-trained one —
it ships with the library and matches our wake word without any training
step, which is the practical, reliable choice for this milestone.
"""
from __future__ import annotations

import asyncio
from typing import AsyncIterator

import numpy as np

from config.settings import settings
from core.logging_setup import log

from audio.microphone import ContinuousMicrophone

SAMPLE_RATE = 16000
FRAME_SAMPLES = 1280  # 80ms at 16kHz — openWakeWord's recommended chunk size


class WakeWordDetector:
    def __init__(self, mic: ContinuousMicrophone) -> None:
        self._model = None
        self._threshold = settings.wake_word_threshold
        self.mic = mic

    def _ensure_model(self):
        if self._model is None:
            import openwakeword
            from openwakeword.model import Model

            log.info("Loading wake-word model (one-time)...")
            # Downloads on first run only; cached locally afterward — no
            # repeated downloads or re-initialization per detection cycle.
            openwakeword.utils.download_models(["hey_jarvis"])
            self._model = Model(wakeword_models=["hey_jarvis"])
        return self._model

    async def listen_for_wake_word(self) -> None:
        """Blocks (in a background thread) until the wake word is detected,
        then returns. Designed to be cheap: runs entirely offline, small
        model, no network calls, no polling beyond reading the mic buffer."""
        model = await asyncio.to_thread(self._ensure_model)
        self.mic.clear()  # Clear stale audio before listening
        log.info("Wake-word model loaded. Actively listening... Say 'Jarvis' to trigger.")
        await asyncio.to_thread(self._listen_blocking, model)

    def _listen_blocking(self, model) -> None:
        while True:
            frame = self.mic.read_samples(FRAME_SAMPLES)
            prediction = model.predict(frame)
            score = prediction.get("hey_jarvis", 0.0)
            if score > self._threshold:
                log.info("Wake word detected (score=%.2f)", score)
                model.reset()  # clear internal state before next listen cycle
                return
