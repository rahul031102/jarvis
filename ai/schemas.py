"""
The complete tool catalogue exposed to the LLM, in OpenAI/Groq function-
calling format (Groq's API is OpenAI-compatible). This is the ONLY
interface the model has to affect the real world — it can never run
arbitrary code.

Each entry here must have a matching implementation in tools/registry.py.
Keep descriptions short and unambiguous; the model relies on them entirely.
"""
from __future__ import annotations

TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "open_application",
            "description": "Open/launch a desktop application by common name (e.g. 'chrome', 'notepad', 'vscode', 'spotify').",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_name": {"type": "string", "description": "Common name of the application."}
                },
                "required": ["app_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "close_application",
            "description": "Close a running application by common name.",
            "parameters": {
                "type": "object",
                "properties": {"app_name": {"type": "string"}},
                "required": ["app_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_url",
            "description": "Open a specific URL in the default (or specified) browser.",
            "parameters": {
                "type": "object",
                "properties": {"url": {"type": "string"}},
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for a query and open the results page in the browser.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "control_volume",
            "description": "Set or adjust the system volume.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["set", "mute", "unmute"]},
                    "level": {"type": "integer", "description": "0-100, required if action is 'set'."},
                },
                "required": ["action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "screenshot",
            "description": "Take a screenshot of the primary display and save it.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_folder",
            "description": "Create a new folder at a given location (e.g. on the Desktop).",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "location": {
                        "type": "string",
                        "description": "One of: desktop, documents, downloads, or an absolute path.",
                    },
                },
                "required": ["name", "location"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "List files/folders in a given directory.",
            "parameters": {
                "type": "object",
                "properties": {"location": {"type": "string"}},
                "required": ["location"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_file",
            "description": "Search for a file by name or pattern within a base directory (e.g. Downloads).",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string"},
                    "location": {"type": "string"},
                },
                "required": ["pattern", "location"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_running_processes",
            "description": "List currently running applications/processes visible to the user.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_path",
            "description": "DANGEROUS: permanently delete a file or folder. Always requires user confirmation.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "system_power",
            "description": "DANGEROUS: shut down, restart, sleep, or lock the computer. Always requires user confirmation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["shutdown", "restart", "sleep", "lock"]},
                },
                "required": ["action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remember",
            "description": "Save a piece of information to persistent memory for future sessions (e.g. 'main project path').",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string"},
                    "value": {"type": "string"},
                },
                "required": ["key", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recall",
            "description": "Retrieve previously remembered information by key, or list all memories if key is omitted.",
            "parameters": {
                "type": "object",
                "properties": {"key": {"type": "string"}},
            },
        },
    },
]

# Tools that are destructive/irreversible and MUST go through the
# confirm-then-execute flow in core/security.py before ever running.
DANGEROUS_TOOLS: set[str] = {"delete_path", "system_power"}
