from __future__ import annotations

import queue
import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000


class ContinuousMicrophone:
    def __init__(self) -> None:
        self._queue: queue.Queue[np.ndarray] = queue.Queue()
        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="int16",
            callback=self._callback
        )
        self._stream.start()

    def _callback(self, indata: np.ndarray, frames: int, time, status) -> None:
        if status:
            import logging
            logging.warning(f"Microphone stream status: {status}")
        self._queue.put(indata.copy())

    def clear(self) -> None:
        """Discard all pending audio in the buffer (e.g. after speaking or processing)."""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

    def read_samples(self, num_samples: int) -> np.ndarray:
        """Block until num_samples are read from the queue and return them.
        Accumulates frames from the callback queue as needed."""
        buffer = []
        samples_accumulated = 0
        while samples_accumulated < num_samples:
            chunk = self._queue.get()  # shape (chunk_frames, 1)
            buffer.append(chunk[:, 0])
            samples_accumulated += chunk.shape[0]

        combined = np.concatenate(buffer)
        if len(combined) > num_samples:
            leftover = combined[num_samples:]
            self._queue.put(leftover[:, np.newaxis])
            return combined[:num_samples]
        return combined

    def close(self) -> None:
        self._stream.stop()
        self._stream.close()
