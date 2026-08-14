"""
Ties everything together: brain -> tool loop -> confirmation gate -> TTS.

This is provider-agnostic about input: `handle_utterance()` takes plain text,
so it works identically whether that text came from voice (STT) or typed
input (useful for testing/dev, and for a future text-chat fallback in the UI).

Performance-relevant design:
- One Brain, one ToolRegistry, one Memory, one TTS instance for the whole
  app lifetime — no re-init per command.
- Each tool call is timed and logged.
- Immediate acknowledgement: for the first tool call in a turn, we speak a
  short "Opening Chrome."-style confirmation as soon as we know the tool
  name/args, IN PARALLEL with actually running it, instead of waiting for
  the tool to finish before saying anything.
"""
from __future__ import annotations

import asyncio
import time

from ai.brain import Brain, ToolCallRequest
from core.errors import ConfirmationRequiredError, to_speakable
from core.logging_setup import log
from core.memory import Memory
from tools.registry import ToolRegistry

# Short, speakable acknowledgements shown immediately when a tool starts,
# so the user never feels like the system is frozen.
IMMEDIATE_ACKS = {
    "open_application": "Opening {app_name}.",
    "close_application": "Closing {app_name}.",
    "open_url": "Opening that page.",
    "web_search": "Searching now.",
    "control_volume": "Adjusting volume.",
    "screenshot": "Taking a screenshot.",
    "create_folder": "Creating that folder.",
    "list_directory": "Checking that folder.",
    "find_file": "Searching for that file.",
    "delete_path": None,  # confirmation flow handles messaging
    "system_power": None,
    "remember": "Saving that.",
    "recall": "Checking my memory.",
    "get_running_processes": "Checking what's running.",
}


class Orchestrator:
    def __init__(self) -> None:
        self.memory = Memory()
        self.brain = Brain()
        self.tools = ToolRegistry(self.memory)
        self._awaiting_confirmation = False

    async def handle_utterance(self, text: str, *, speak: callable) -> str:
        """Process one user utterance end-to-end. `speak` is an async
        callable(str) -> None used for both immediate acks and final replies."""
        start = time.monotonic()
        log.info("Command recognized: %s", text)

        # If we're waiting on a yes/no for a dangerous action, handle that first.
        if self._awaiting_confirmation:
            return await self._resolve_confirmation(text, speak=speak)

        response = await self.brain.think(text)
        final_text = await self._run_tool_loop(response, speak=speak)

        elapsed_ms = (time.monotonic() - start) * 1000
        log.info("Total command latency: %.0fms", elapsed_ms)

        if final_text:
            await speak(final_text)
        return final_text or ""

    async def _run_tool_loop(self, response, *, speak) -> str | None:
        while response.tool_calls:
            tool_results = []
            for call in response.tool_calls:
                result_text = await self._execute_one_tool(call, speak=speak)
                if result_text is None:
                    # A confirmation was requested; halt the loop here and
                    # wait for the user's next utterance.
                    return None
                tool_results.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": result_text,
                    }
                )
            response = await self.brain.continue_with_tool_results(
                response.raw_assistant_message, tool_results
            )
        return response.text

    async def _execute_one_tool(self, call: ToolCallRequest, *, speak) -> str | None:
        log.info("Tool selected: %s(%s)", call.name, call.input)

        # Speak an immediate ack in parallel with execution (non-blocking feel).
        ack_template = IMMEDIATE_ACKS.get(call.name)
        ack_task = None
        if ack_template:
            try:
                ack_text = ack_template.format(**call.input)
            except (KeyError, IndexError):
                ack_text = ack_template
            ack_task = asyncio.create_task(speak(ack_text))

        try:
            result = await self.tools.execute(call.name, call.input)
        except ConfirmationRequiredError as exc:
            if ack_task:
                await ack_task
            self._awaiting_confirmation = True
            self._pending_tool_name = call.name
            await speak(exc.speakable_message)
            return None
        except Exception as exc:
            if ack_task:
                await ack_task
            message = to_speakable(exc)
            log.warning("Tool '%s' failed: %s", call.name, message)
            return f"(failed: {message})"

        if ack_task:
            await ack_task
        log.info("Action completed: %s", call.name)
        return result

    async def _resolve_confirmation(self, text: str, *, speak) -> str:
        self._awaiting_confirmation = False
        affirmative = text.strip().lower() in (
            "yes", "yeah", "yep", "confirm", "do it", "go ahead", "continue",
        )
        approved = self.tools.security.confirm_and_check(affirmative)

        if not approved:
            await speak("Okay, I won't do that.")
            return "Okay, I won't do that."

        try:
            result = await self.tools.execute(
                approved["tool_name"], approved["args"], skip_confirmation_check=True
            )
        except Exception as exc:
            message = to_speakable(exc)
            await speak(message)
            return message

        await speak(result)
        return result

    async def stop_speaking(self, tts) -> None:
        await tts.stop()
