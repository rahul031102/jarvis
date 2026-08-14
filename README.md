# JARVIS — Milestone 1: Core Loop (text-mode, real tools, real security)

This is **not a demo** — every tool in this milestone actually executes on your
Windows machine. This is the first of several milestones described in the
original spec. It's deliberately scoped down so it's fully testable before we
add wake-word detection and the desktop UI.

## What's real right now

- **Claude tool-calling brain** (`ai/brain.py`) — full multi-step tool loop, short
  conversation context, no unbounded history growth.
- **6 real tools**: `open_application`, `close_application`, `open_url`,
  `web_search`, `control_volume` (real Windows Core Audio via pycaw),
  `screenshot` (real, via mss), plus filesystem tools (`create_folder`,
  `list_directory`, `find_file`, `delete_path`) and `system_power`.
- **Security gate** (`core/security.py`) — argument allowlisting per tool,
  protected-path checks, and a genuine confirm-before-execute flow for
  `delete_path` and `system_power`. Verified with automated tests — see below.
- **Persistent memory** (`core/memory.py`) — SQLite-backed `remember` / `recall`.
- **Text-to-speech** (`audio/text_to_speech.py`) — edge-tts, cancellable
  mid-sentence (the "stop" requirement).
- **Speech-to-text** (`audio/speech_to_text.py`) — faster-whisper + WebRTC VAD
  for automatic end-of-speech detection.
- **Wake word** (`audio/wake_word.py`) — offline openWakeWord using the
  pre-trained "hey_jarvis" model, no cloud calls, ~80ms frame processing.
- **Full voice loop** (`main.py`) — wake word → beep → record → transcribe →
  brain/tools → speak → back to listening. This is the real thing from the
  spec, not text-mode anymore.
- **Structured logging** — see `logs/jarvis.log`.

## Run voice mode

```bash
python main.py
```

Say "Jarvis" — you'll hear a short beep — then speak your command. JARVIS
transcribes, executes, replies out loud, and returns to low-resource
wake-word listening automatically. Say "Jarvis, stop" to interrupt and cancel
whatever it's currently speaking or doing.

**Known limitation, stated plainly rather than faked:** interrupting JARVIS
*while it is actively speaking* (true barge-in) isn't reliable yet without
echo cancellation, because the wake-word listener would otherwise pick up
JARVIS's own voice through the speakers. "Stop" works reliably as a command
said right after a fresh wake-word trigger. Full barge-in during playback is
a planned follow-up (needs AEC — acoustic echo cancellation — which is a
real, non-trivial addition, not a quick toggle).

## Text mode (still available, useful for fast iteration)

```bash
python run.py
python run.py --no-speech   # print instead of speak replies
```

Text mode calls the exact same `orchestrator.handle_utterance()` that voice
mode uses — nothing above the STT/TTS layer differs between the two.

## What's NOT built yet (next milestones, in order)
18. Screen awareness / OCR
19. Playwright-based browser automation (reading page content, not just opening URLs)
20. PyQt6 desktop UI
21. Multi-step project-runner ("open project, install deps, start server, verify")
22. True barge-in (AEC) during active TTS playback

I'm not stubbing these — they simply aren't in this milestone. `run.py` today
gives you a **typed** JARVIS so you can validate the brain/tools/security
pipeline end-to-end before we add the mic.

## Setup

```bash
cd jarvis
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt

copy .env.example .env
# then edit .env and set GROQ_API_KEY (free at https://console.groq.com)
```

**LLM provider: Groq (for testing).** This build uses Groq's API — free tier,
no credit card, very fast inference. It's OpenAI-compatible, so the brain
(`ai/brain.py`) uses the `groq` Python package and OpenAI-format function
calling under the hood. Default model is `openai/gpt-oss-120b`, Groq's
current recommendation for tool-use reliability; change `GROQ_MODEL` in
`.env` to try others (e.g. `qwen/qwen3.6-27b`).

Swapping back to a different provider later only touches `ai/brain.py` and
`ai/schemas.py` (tool format differs slightly between providers) — nothing
in `tools/`, `core/`, or `audio/` needs to change, since the orchestrator
only depends on `Brain.think()` / `Brain.continue_with_tool_results()`
returning a `BrainResponse`.

Note: `pycaw`, `pywinauto`, and `comtypes` are Windows-only and will fail to
install on macOS/Linux — this project targets Windows per the spec.

## Run it

```bash
python run.py
```

Try:
```
> open chrome
> search for MediaPipe
> take a screenshot
> remember my main project is C:\Projects\JARVIS
> what's my main project
> delete C:\Users\you\Desktop\junk
  (JARVIS will ask you to confirm before doing anything)
> what applications are running
```

Use `python run.py --no-speech` to print replies instead of speaking them
(useful if you don't want audio during dev).

## Run the tests

```bash
pip install pytest pytest-asyncio
python -m pytest tests/ -v
```

15 tests currently cover:
- Security validation (argument allowlisting, protected paths, URL/app-name sanitization)
- The confirm-then-execute flow for dangerous tools, including the "user says no" path
- Memory persistence and updates
- The orchestrator's full tool-call loop using a stubbed brain (no API calls needed)
- The voice loop's cycle control flow (wake → listen → transcribe → process →
  speak) and the stop-phrase interruption path, using stubbed audio components
  so tests run without a microphone/speaker

## Performance notes already in place

- Brain, ToolRegistry, Memory, and TTS are constructed **once** at startup —
  no re-initialization per command.
- Every tool call is timed and logged (`Tool 'x' completed in Nms`).
- The orchestrator speaks an immediate acknowledgement ("Opening Chrome.") in
  parallel with actually executing the tool — you're never staring at silence.
- faster-whisper's model is lazy-loaded once on first use and reused for
  every subsequent transcription.

## Why text-mode first

Wake-word + STT + TTS + UI all at once means if something's broken you can't
tell whether it's the mic, the model, or the tool layer. Text-mode isolates
the brain/tools/security stack completely. Once you confirm this works for
your real commands, I'll wire in the wake-word listener and swap `input()`
for the VAD-based recorder in `audio/speech_to_text.py` — same
`orchestrator.handle_utterance()` call underneath, so nothing above it changes.
