from __future__ import annotations

import queue
import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000


class ContinuousMicrophone:
    def __init__(self) -> None:
        self._queue: queue.Queue[np.ndarray] = queue.Queue()
        self._leftover: np.ndarray | None = None
        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="int16",
            blocksize=480,  # 30ms frames at 16kHz
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
        self._leftover = None
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

    def read_samples(self, num_samples: int) -> np.ndarray:
        """Block until num_samples are read from the queue and return them.
        Accumulates frames from the callback queue as needed. Drops old frames if lag is detected."""
        # Lag compensation: 10 chunks of 480 samples is ~300ms of latency.
        # If we exceed this, drop older chunks to stay in real-time.
        if self._queue.qsize() > 10:
            while self._queue.qsize() > 2:
                try:
                    self._queue.get_nowait()
                except queue.Empty:
                    break
            self._leftover = None

        buffer = []
        samples_accumulated = 0
        
        if self._leftover is not None:
            buffer.append(self._leftover)
            samples_accumulated += len(self._leftover)
            self._leftover = None

        while samples_accumulated < num_samples:
            chunk = self._queue.get()  # shape (chunk_frames, 1)
            if chunk is None:
                raise RuntimeError("Microphone closed")
            buffer.append(chunk[:, 0])
            samples_accumulated += chunk.shape[0]

        combined = np.concatenate(buffer)
        if len(combined) > num_samples:
            self._leftover = combined[num_samples:]
            return combined[:num_samples]
        return combined

    def close(self) -> None:
        self._stream.stop()
        self._stream.close()
        self._queue.put(None)  # Sentinel to unblock read_samples waiting in background threads
