"""
Full voice JARVIS. This is the real thing described in the spec:

    wake word -> confirmation beep -> record command -> transcribe ->
    brain/tools -> speak reply -> back to low-resource wake-word listening

Runs three loosely-coupled async tasks:
  1. Wake-word listener (only active when we're not already in a command)
  2. Command processing (STT -> orchestrator -> TTS)
  3. A lightweight "stop" watcher isn't a separate task — interruption is
     handled by re-triggering the wake word mid-speech (see note below).

Note on interruption: robustly detecting "Jarvis, stop" WHILE Jarvis is
speaking (and while your own TTS audio is playing through speakers) needs
either echo cancellation or a push-to-interrupt hardware signal — a plain
wake-word model listening over your own TTS output will pick up false
triggers or miss real ones. For this milestone, "stop" works reliably in
two situations, which covers the real usage pattern:
  (a) said as the command right after a wake-word trigger, and
  (b) typed / triggered via the text-mode fallback (run.py) at any time.
Full always-on barge-in during active playback is flagged as a known
limitation below rather than faked.
"""
from __future__ import annotations

import asyncio

from audio.cues import play_done_cue, play_wake_cue
from audio.microphone import ContinuousMicrophone
from audio.speech_to_text import SpeechToText
from audio.text_to_speech import TextToSpeech
from audio.wake_word import WakeWordDetector
from core.errors import to_speakable
from core.logging_setup import log
from core.orchestrator import Orchestrator

STOP_PHRASES = {"stop", "jarvis stop", "cancel", "cancel that", "never mind"}


class VoiceJarvis:
    def __init__(self) -> None:
        self.mic = ContinuousMicrophone()
        self.orchestrator = Orchestrator()
        self.stt = SpeechToText(self.mic)
        self.tts = TextToSpeech()
        self.wake_word = WakeWordDetector(self.mic)

    async def speak(self, text: str) -> None:
        print(f"JARVIS: {text}")
        await self.tts.speak(text)

    async def run_forever(self) -> None:
        log.info("JARVIS voice loop starting. Listening for wake word 'Jarvis'...")
        continuous_listen = False
        while True:
            try:
                if not continuous_listen:
                    await self.wake_word.listen_for_wake_word()
                    await play_wake_cue()
                    log.info("Listening")
                
                try:
                    max_wait = 10.0 if continuous_listen else 15.0
                    text = await self.stt.record_and_transcribe(max_wait_seconds=max_wait)
                except Exception:
                    if continuous_listen:
                        # Silently time out and go back to wake word mode
                        log.info("No follow-up speech detected. Returning to wake-word mode.")
                        continuous_listen = False
                    else:
                        log.info("No speech detected.")
                    continue

                log.info("Command recognized: %s", text)

                if text.strip().lower() in STOP_PHRASES:
                    await self.tts.stop()
                    log.info("Speech/action stop requested.")
                    continuous_listen = False
                    continue

                await self.orchestrator.handle_utterance(text, speak=self.speak)
                await play_done_cue()
                
                # Keep conversation going without needing wake word
                continuous_listen = True
                log.info("Wake-word bypassed. Actively listening for follow-up...")

            except KeyboardInterrupt:
                break
            except Exception as exc:  # never let one bad cycle kill the whole assistant
                log.exception("Unhandled error in voice cycle")
                await self.speak(to_speakable(exc))
                continuous_listen = False


async def main() -> None:
    jarvis = VoiceJarvis()
    try:
        await jarvis.run_forever()
    finally:
        jarvis.mic.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nJARVIS shutting down.")
