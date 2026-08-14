"""
Text-mode JARVIS. Type commands, get real tool execution and spoken (or
printed) replies. This is the fastest way to verify the brain + tools +
security pipeline end-to-end before wiring in voice.

Run:  python run.py
Run:  python run.py --no-speech   (prints replies instead of speaking them)
"""
from __future__ import annotations

import argparse
import asyncio

from core.logging_setup import log
from core.orchestrator import Orchestrator


async def main(use_speech: bool) -> None:
    orchestrator = Orchestrator()

    tts = None
    if use_speech:
        from audio.text_to_speech import TextToSpeech

        tts = TextToSpeech()

    async def speak(text: str) -> None:
        print(f"JARVIS: {text}")
        if tts:
            await tts.speak(text)

    print("JARVIS text-mode ready. Type a command ('quit' to exit, 'stop' to cancel speech).")
    while True:
        try:
            user_input = await asyncio.to_thread(input, "> ")
        except (EOFError, KeyboardInterrupt):
            break

        if user_input.strip().lower() in ("quit", "exit"):
            break
        if user_input.strip().lower() == "stop" and tts:
            await tts.stop()
            continue
        if not user_input.strip():
            continue

        try:
            await orchestrator.handle_utterance(user_input, speak=speak)
        except Exception as exc:  # top-level safety net — never crash the loop
            log.exception("Unhandled error in main loop")
            print(f"JARVIS: Something went wrong: {exc}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-speech", action="store_true", help="Print replies instead of speaking them.")
    args = parser.parse_args()
    asyncio.run(main(use_speech=not args.no_speech))
