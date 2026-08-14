"""
Very short audio cues, synthesized on the fly (no external sound-asset
files to manage/ship). Used to give immediate feedback: a rising beep when
the wake word is detected, so the user knows to start talking without
waiting on any TTS.
"""
from __future__ import annotations

import asyncio

import numpy as np

SAMPLE_RATE = 16000


def _tone(freq: float, duration_s: float, volume: float = 0.2) -> np.ndarray:
    t = np.linspace(0, duration_s, int(SAMPLE_RATE * duration_s), endpoint=False)
    envelope = np.minimum(1.0, np.minimum(t / 0.01, (duration_s - t) / 0.01))
    return (np.sin(2 * np.pi * freq * t) * envelope * volume).astype(np.float32)


_WAKE_CUE = _tone(880, 0.12)
_DONE_CUE = _tone(440, 0.08)


async def play_wake_cue() -> None:
    await asyncio.to_thread(_play, _WAKE_CUE)


async def play_done_cue() -> None:
    await asyncio.to_thread(_play, _DONE_CUE)


def _play(samples: np.ndarray) -> None:
    import sounddevice as sd

    sd.play(samples, samplerate=SAMPLE_RATE)
    sd.wait()
