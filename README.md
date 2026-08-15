# JARVIS

A voice-controlled Windows desktop assistant. Every tool below actually
executes on your machine — nothing here is a stub or a fake demo response.

## What it can do right now

**Core control**
- Open/close applications by name
- Open URLs, web search
- System volume control (real Windows Core Audio via pycaw)
- Screenshots
- Create folders, list directories, find files
- Delete files/folders — **always asks for confirmation first**
- Shutdown/restart/sleep/lock — **also confirmation-gated**
- Persistent memory (remember/recall facts across sessions)
- Multi-step chaining in one request ("open chrome and search for X")

**Screen awareness (new)**
- `read_screen` — captures the screen and OCRs any visible text, so you can
  ask "what error is showing", "what does this popup say", "read my screen."
  Only triggers on-demand, never polls continuously.
  Requires the Tesseract OCR binary installed separately (not just pip) —
  see `.env.example` for the install link. If it's missing, JARVIS tells you
  clearly instead of crashing.

**Project runner (new — the flagship "real agent" feature)**
- `start_project` — point it at a project folder. It detects Node
  (package.json) or Python (requirements.txt/pyproject.toml), installs
  dependencies **only if missing**, starts the dev server or entry point,
  and honestly reports whether it survived its startup window or crashed
  (with the actual error output, not a guess).
- `stop_project` — stops a server JARVIS started.
- Example: *"Jarvis, open my project and start the server"* → JARVIS says
  "Opening the project." immediately (non-blocking), then does the
  install/start work in the background and reports the real outcome.
- Honesty note: this can't guarantee a dev server is "fully up and serving
  requests" — that would need knowing its port/framework/health endpoint.
  What it verifies is real: did the process survive its own crash window.
  Stated plainly rather than faked.

**Voice**
- Wake word "Jarvis" (offline, openWakeWord)
- Auto end-of-speech detection (no push-to-talk)
- Continuous-listen follow-up mode: after JARVIS finishes a reply, it keeps
  listening for a few seconds so a natural follow-up doesn't need the wake
  word repeated
- "Stop"/"cancel" interrupts speech and returns to wake-word mode
- Real-time lag-compensated microphone buffering (drops stale audio if
  processing falls behind, so JARVIS doesn't respond to delayed backlog)

## Not built yet
- Desktop GUI (PyQt6)
- Playwright-based browser automation (reading page content, not just
  opening URLs — currently browser tools only open pages/search)
- True barge-in (interrupting JARVIS mid-sentence while actively speaking) —
  needs echo cancellation, a real non-trivial addition

## Setup

```bash
cd jarvis
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

copy .env.example .env
# set GROQ_API_KEY (free at https://console.groq.com)
```

For screen awareness, also install Tesseract OCR (the binary, separately
from pip): https://github.com/UB-Mannheim/tesseract/wiki

For the project runner, `npm`/`node` and/or `python`/`pip` need to be on
PATH, whichever project types you use it on.

## Run it

```bash
python run.py     # text mode — fastest for testing, no mic needed
python main.py    # full voice mode
```

## Run the tests

```bash
pip install pytest pytest-asyncio
python -m pytest tests/ -v
```

35 tests covering: security validation and the confirm-then-execute flow,
memory persistence, the orchestrator's tool loop, the project runner's
decision logic and crash/failure reporting (mocked subprocesses — no real
npm/pip run needed to verify the logic), and screen-reading's empty/
truncation handling. Two additional voice-loop tests exist but need a real
audio device to run (they exercise sounddevice/PortAudio directly).

## Architecture note on security

The LLM never runs arbitrary commands — including in the new project
runner. It only ever supplies a *folder path*; every actual subprocess
command (npm install, npm run dev, pip install, python app.py) is chosen
by fixed code logic based on what manifest files exist in that folder,
never a string the model composes. Same rule as every other tool in this
project.
