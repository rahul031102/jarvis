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
    {
        "type": "function",
        "function": {
            "name": "read_screen",
            "description": (
                "Capture the current screen and read any visible text via OCR "
                "(e.g. to answer 'what error is showing', 'what does this popup say', "
                "'read the text on my screen'). Only call this when the user's request "
                "actually needs to know what's visually on screen."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "start_project",
            "description": (
                "Open a software project by folder path, install its dependencies if "
                "missing (npm install / pip install -r requirements.txt), start its dev "
                "server or main entry point, and report whether it's running. Works for "
                "Node projects (package.json) and Python projects (requirements.txt / "
                "pyproject.toml)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute path to the project's root folder."}
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "stop_project",
            "description": "Stop a project's server that was previously started with start_project.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute path to the project's root folder."}
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_open_windows",
            "description": "List the titles of all currently open application windows (what's on the taskbar/alt-tab list right now).",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_active_window",
            "description": "Get the title of whichever window currently has focus.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "focus_window",
            "description": "Bring a specific open window/app to the foreground so subsequent typing or clicking lands in it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Window title or app name to switch to (e.g. 'notepad', 'vs code')."}
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_window_text",
            "description": "Read the actual text content inside a specific window (editors, dialogs, forms) via its accessibility tree — more reliable than reading the screen visually for real text content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Window title or app name to read from."}
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "type_text",
            "description": "Type text into whatever currently has keyboard focus. Call focus_window first if you need to target a specific app.",
            "parameters": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "press_key",
            "description": "Press a single key (e.g. 'enter', 'tab', 'esc', 'backspace', an arrow key, or a letter/number).",
            "parameters": {
                "type": "object",
                "properties": {"key": {"type": "string"}},
                "required": ["key"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "hotkey",
            "description": "Press a key combination, e.g. ['ctrl','s'] for Ctrl+S, ['ctrl','shift','t'] for Ctrl+Shift+T.",
            "parameters": {
                "type": "object",
                "properties": {
                    "keys": {"type": "array", "items": {"type": "string"}, "description": "2-4 keys to press together."}
                },
                "required": ["keys"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "move_mouse",
            "description": "Move the mouse cursor to a specific screen coordinate.",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                },
                "required": ["x", "y"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "click",
            "description": "Click the mouse. If x/y are omitted, clicks at the current cursor position. Prefer click_control when the user names a specific button/element instead.",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                    "button": {"type": "string", "enum": ["left", "right", "middle"]},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "click_control",
            "description": (
                "Click a named button/control inside a specific window by its visible text "
                "(e.g. click_control('Notepad', 'Save')) — reliable, no coordinates needed. "
                "Use this instead of click() whenever the user names what they want clicked."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "app_name": {"type": "string", "description": "Window title or app name."},
                    "control_text": {"type": "string", "description": "Visible text of the button/control to click."},
                },
                "required": ["app_name", "control_text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_whatsapp_message",
            "description": "Send a WhatsApp message directly to a contact by name (opens WhatsApp, searches contact, types, and sends). Very fast.",
            "parameters": {
                "type": "object",
                "properties": {
                    "contact_name": {"type": "string", "description": "The name of the contact as saved in WhatsApp."},
                    "message": {"type": "string", "description": "The message text to send."}
                },
                "required": ["contact_name", "message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "forward_whatsapp_media",
            "description": "Forward the last message or photo from a sender's chat to another recipient on WhatsApp. Very fast.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sender_name": {"type": "string", "description": "The name of the sender who sent the photo/message."},
                    "recipient_name": {"type": "string", "description": "The name of the contact to forward it to."}
                },
                "required": ["sender_name", "recipient_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_website_or_search",
            "description": "Open a website directly if a domain name is given (e.g. 'github.com'), otherwise searches Google in Chrome.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Website URL or search term."}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "control_browser_tabs",
            "description": "Manage Chrome tabs instantly using simulated keyboard shortcuts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["new_tab", "close_tab", "next_tab", "prev_tab", "focus_tab"]},
                    "tab_name": {"type": "string", "description": "The name of the tab to focus (required for focus_tab action)."}
                },
                "required": ["action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "play_music",
            "description": "Search and play a song/artist directly on Spotify (or fallback to YouTube).",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The song title, artist, or playlist name."}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "quick_note",
            "description": "Quickly write or append a short note to notes.txt on the user's Desktop.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "The note text to append."}
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_file",
            "description": "Write a new text or code file with specified file content instantly.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "The absolute path where the file will be saved."},
                    "content": {"type": "string", "description": "The content of the file."}
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_system_folder",
            "description": "Open standard Windows directories (Downloads, Documents, Desktop, Pictures, Music, Videos) directly in File Explorer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "folder_name": {"type": "string", "description": "Name of the folder or absolute path."}
                },
                "required": ["folder_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_and_open_file",
            "description": "Search and open a file matching a pattern from common user folders directly in its default program.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "Fuzzy pattern to find the file name."}
                },
                "required": ["filename"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "media_control",
            "description": "Trigger global media controls (play/pause, skip, mute) for system audio players.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["play_pause", "next_track", "prev_track", "mute"]}
                },
                "required": ["action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "window_action",
            "description": "Perform basic window actions like maximize, minimize, close, or show desktop.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["show_desktop", "maximize", "minimize", "close"]}
                },
                "required": ["action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_system_status",
            "description": "Retrieve current CPU load, memory utilization, disk space, and battery status.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "Evaluate basic mathematical expressions in Python and return the answer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {"type": "string", "description": "Expression containing numbers and operators +, -, *, /, %, (, )."}
                },
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_whatsapp_chat",
            "description": "Switch focus to WhatsApp and directly search and open a contact's chat thread by name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "contact_name": {"type": "string", "description": "Exact display name of the contact or chat group to search for and open."}
                },
                "required": ["contact_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_instagram_message",
            "description": "Send a direct message to a user on Instagram Web using native keyboard cycling.",
            "parameters": {
                "type": "object",
                "properties": {
                    "username": {"type": "string", "description": "The exact Instagram username of the recipient."},
                    "message": {"type": "string", "description": "The text message content to send."}
                },
                "required": ["username", "message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_instagram_reel",
            "description": "Open Instagram Reels, copy the active reel's URL, and send it directly to a user in DMs where Instagram automatically renders it as a native playable bubble.",
            "parameters": {
                "type": "object",
                "properties": {
                    "username": {"type": "string", "description": "The exact Instagram username of the recipient."},
                    "topic": {"type": "string", "description": "Optional keyword/topic of the reel (defaults to comedy)."}
                },
                "required": ["username"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "navigate_to",
            "description": "Open a URL in JARVIS's dedicated browser automation profile (separate from the person's regular browser) and wait for it to load.",
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
            "name": "read_page_content",
            "description": "Read the visible text content of the currently open page in JARVIS's browser automation profile — real page text, not a screenshot.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "click_web_element",
            "description": "Click a button or link on the current page by its visible text.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "The visible text of the button/link to click."}
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fill_web_form_field",
            "description": "Fill a form field on the current page, found by its visible label or placeholder text.",
            "parameters": {
                "type": "object",
                "properties": {
                    "label": {"type": "string", "description": "The visible label or placeholder of the field, e.g. 'Full Name', 'Email address'."},
                    "value": {"type": "string"},
                },
                "required": ["label", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "upload_file_to_form",
            "description": "Upload a local file to a file-upload field on the current page, found by its visible label.",
            "parameters": {
                "type": "object",
                "properties": {
                    "label": {"type": "string", "description": "The visible label of the upload field, e.g. 'Resume', 'Cover Letter'."},
                    "file_path": {"type": "string", "description": "Absolute path to the local file to upload."},
                },
                "required": ["label", "file_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "submit_web_form",
            "description": (
                "DANGEROUS: submits the current web form/application. Irreversible — always requires "
                "the user's explicit confirmation. Only call this when the user has clearly asked to "
                "submit or apply, never speculatively as part of filling out a form."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_profile_field",
            "description": "Save a piece of personal information (name, email, phone, resume file path, etc.) for later use auto-filling web forms.",
            "parameters": {
                "type": "object",
                "properties": {
                    "field": {"type": "string", "description": "Field name, e.g. 'full_name', 'email', 'phone', 'resume_path'."},
                    "value": {"type": "string"},
                },
                "required": ["field", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_profile",
            "description": "Retrieve all saved personal information fields, e.g. before filling out a form.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]

# Tools that are destructive/irreversible and MUST go through the
# confirm-then-execute flow in core/security.py before ever running.
DANGEROUS_TOOLS: set[str] = {
    "delete_path",
    "system_power",
    "send_whatsapp_message",
    "forward_whatsapp_media",
    "submit_web_form",
    "send_instagram_message",
    "send_instagram_reel",
}
