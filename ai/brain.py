"""
The reasoning layer. Wraps the Groq client (OpenAI-compatible chat
completions API), keeps a short-lived conversation buffer, and returns
either a final text reply or a list of tool calls for the orchestrator to
execute.

Design notes:
- One persistent AsyncGroq client (no re-init per call).
- Context is trimmed to the last N turns — no unbounded history growth.
- The model can request MULTIPLE tool calls in one turn; the orchestrator
  runs them, feeds results back, and the loop continues until the model
  produces a final text-only reply (standard tool-use loop).
- Groq's API is OpenAI-compatible: tool calls arrive as
  response.choices[0].message.tool_calls, each with .id, .function.name,
  and .function.arguments (a JSON string, not a dict — parsed here).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from groq import AsyncGroq

from ai.prompts import SYSTEM_PROMPT
from ai.schemas import TOOLS
from config.settings import settings

MAX_CONTEXT_TURNS = 12


@dataclass
class ToolCallRequest:
    id: str
    name: str
    input: dict


@dataclass
class BrainResponse:
    text: str | None
    tool_calls: list[ToolCallRequest] = field(default_factory=list)
    raw_assistant_message: dict | None = None  # needed to continue the tool loop


class Brain:
    def __init__(self) -> None:
        if not settings.groq_api_key:
            raise RuntimeError("GROQ_API_KEY is not set. Add it to your .env file.")
        self._client = AsyncGroq(api_key=settings.groq_api_key)
        self._history: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]

    def reset_context(self) -> None:
        self._history = [{"role": "system", "content": SYSTEM_PROMPT}]

    def _trim_history(self) -> None:
        # Keep the system message plus the last N turns.
        if len(self._history) > MAX_CONTEXT_TURNS * 2 + 1:
            self._history = [self._history[0]] + self._history[-(MAX_CONTEXT_TURNS * 2):]

    async def think(self, user_text: str) -> BrainResponse:
        self._history.append({"role": "user", "content": user_text})
        self._trim_history()
        return await self._call_model()

    async def continue_with_tool_results(self, assistant_message: dict, tool_results: list[dict]) -> BrainResponse:
        """Feed tool results back to the model to continue the same turn.
        tool_results items must be OpenAI-format: {"role": "tool",
        "tool_call_id": ..., "content": ...}."""
        self._history.append(assistant_message)
        self._history.extend(tool_results)
        self._trim_history()
        return await self._call_model()

    async def _call_model(self) -> BrainResponse:
        response = await self._client.chat.completions.create(
            model=settings.groq_model,
            max_tokens=1024,
            tools=TOOLS,
            tool_choice="auto",
            messages=self._history,
        )

        message = response.choices[0].message
        tool_calls: list[ToolCallRequest] = []
        if message.tool_calls:
            for tc in message.tool_calls:
                try:
                    args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                except json.JSONDecodeError:
                    args = {}
                tool_calls.append(ToolCallRequest(id=tc.id, name=tc.function.name, input=args))

        assistant_message = {
            "role": "assistant",
            "content": message.content,
        }
        if message.tool_calls:
            assistant_message["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in message.tool_calls
            ]

        if not tool_calls:
            # Final reply — commit it to history.
            self._history.append(assistant_message)

        return BrainResponse(
            text=message.content,
            tool_calls=tool_calls,
            raw_assistant_message=assistant_message,
        )
