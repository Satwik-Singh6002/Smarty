"""
Text-based Chat Loop for Smarty V2 using OpenRouter
Replaces the audio-based Gemini Native Audio loop with text chat.
"""
import asyncio
import os
import json
from typing import Optional, Callable, Dict, Any, List
from dotenv import load_dotenv

from openrouter_client import OpenRouterClient, convert_gemini_tools_to_openai

load_dotenv()

# Import agents
from cad_agent import CadAgent
from web_agent import WebAgent
from kasa_agent import KasaAgent
from printer_agent import PrinterAgent
from project_manager import ProjectManager


# Tool definitions for OpenAI format
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "generate_cad",
            "description": "Generates a 3D CAD model based on a prompt.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "The description of the object to generate."}
                },
                "required": ["prompt"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "iterate_cad",
            "description": "Modifies or iterates on the current CAD design based on user feedback.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "The changes or modifications to apply to the current design."}
                },
                "required": ["prompt"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_web_agent",
            "description": "Opens an automated web browser and performs complex multi-step interactions like clicking, logging in, or filling out forms. CRITICAL: DO NOT use this tool for answering basic questions, retrieving summary info, or doing a simple web search. Only use if the user explicitly asks you to 'use the web agent' or perform a complex browser task.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "The detailed instructions for the web browser agent."}
                },
                "required": ["prompt"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_project",
            "description": "Creates a new project folder to organize files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "The name of the new project."}
                },
                "required": ["name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "switch_project",
            "description": "Switches the current active project context.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "The name of the project to switch to."}
                },
                "required": ["name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_projects",
            "description": "Lists all available projects.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_smart_devices",
            "description": "Lists all available smart home devices on the network.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "control_light",
            "description": "Controls a smart light device.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {"type": "string", "description": "The IP address of the device to control."},
                    "action": {"type": "string", "description": "The action: 'turn_on', 'turn_off', or 'set'."},
                    "brightness": {"type": "integer", "description": "Optional brightness level (0-100)."},
                    "color": {"type": "string", "description": "Optional color name (e.g., 'red', 'warm')."}
                },
                "required": ["target", "action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "discover_printers",
            "description": "Discovers 3D printers available on the local network.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "print_stl",
            "description": "Prints an STL file to a 3D printer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "stl_path": {"type": "string", "description": "Path to STL file, or 'current' for the most recent CAD model."},
                    "printer": {"type": "string", "description": "Printer name or IP address."},
                    "profile": {"type": "string", "description": "Optional slicer profile name."}
                },
                "required": ["stl_path", "printer"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_print_status",
            "description": "Gets the current status of a 3D printer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "printer": {"type": "string", "description": "Printer name or IP address."}
                },
                "required": ["printer"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "open_url",
            "description": "Opens a URL or website in the user's default browser. Use this when the user asks to 'open Google', 'go to YouTube', 'open a website', 'search for something', 'search youtube', etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The URL to open. Can be a full URL, Google search 'search: query', or Youtube search 'ytsearch: query'"}
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "trigger_overload_protocol",
            "description": "Activates the system's hyper-drive / overload protocol. This enters a red alert state, flashes smart home lights red/orange, and supercharges the interface. Use this when the user requests 'overload mode', 'red alert', 'self-destruct', or 'supercharge the core'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "active": {"type": "boolean", "description": "Whether to turn the overload protocol ON (true) or OFF (false)."}
                },
                "required": ["active"]
            }
        }
    },
    # ===== SYSTEM TOOLS =====
    {"type": "function", "function": {"name": "get_time", "description": "Gets the current time.", "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {"name": "get_date", "description": "Gets the current date and day of week.", "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {"name": "take_screenshot", "description": "Takes a screenshot of the screen.", "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {"name": "volume_control", "description": "Controls system volume: up, down, mute, max, min.", "parameters": {"type": "object", "properties": {"action": {"type": "string", "description": "Action: 'up','down','mute','max','min'"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "lock_computer", "description": "Locks the computer screen.", "parameters": {"type": "object", "properties": {}, "required": []}}},
    # ===== APP MANAGEMENT =====
    {"type": "function", "function": {"name": "open_application", "description": "Opens a local application like notepad, chrome, vscode, spotify, discord, etc.", "parameters": {"type": "object", "properties": {"app_name": {"type": "string", "description": "Name of the application"}}, "required": ["app_name"]}}},
    {"type": "function", "function": {"name": "close_application", "description": "Force closes an application. Use when user says 'close chrome', 'band karo notepad', etc.", "parameters": {"type": "object", "properties": {"app_name": {"type": "string", "description": "Name of the application to close"}}, "required": ["app_name"]}}},
    # ===== CLIPBOARD =====
    {"type": "function", "function": {"name": "copy_to_clipboard", "description": "Copies text to the clipboard.", "parameters": {"type": "object", "properties": {"text": {"type": "string", "description": "Text to copy"}}, "required": ["text"]}}},
    {"type": "function", "function": {"name": "get_clipboard", "description": "Gets current clipboard content.", "parameters": {"type": "object", "properties": {}, "required": []}}},
    # ===== KEYBOARD & TYPING =====
    {"type": "function", "function": {"name": "type_text", "description": "Types text as keyboard input into the active window.", "parameters": {"type": "object", "properties": {"text": {"type": "string", "description": "Text to type"}}, "required": ["text"]}}},
    {"type": "function", "function": {"name": "press_hotkey", "description": "Presses a keyboard shortcut like ctrl+c, alt+tab, win+d, ctrl+shift+esc, etc.", "parameters": {"type": "object", "properties": {"keys": {"type": "string", "description": "Hotkey combo e.g. 'ctrl+c', 'alt+tab', 'win+d'"}}, "required": ["keys"]}}},
    {"type": "function", "function": {"name": "press_key", "description": "Presses a single key like enter, escape, space, f5, etc.", "parameters": {"type": "object", "properties": {"key": {"type": "string", "description": "Key to press"}}, "required": ["key"]}}},
    # ===== WINDOW MANAGEMENT =====
    {"type": "function", "function": {"name": "minimize_all_windows", "description": "Minimizes all windows (show desktop). Use for 'show desktop', 'minimize all'.", "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {"name": "switch_window", "description": "Switches to the next open window (Alt+Tab).", "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {"name": "maximize_window", "description": "Maximizes the current window.", "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {"name": "minimize_window", "description": "Minimizes the current window.", "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {"name": "close_window", "description": "Closes the current active window (Alt+F4).", "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {"name": "snap_window", "description": "Snaps the current window to left/right/up/down half of screen.", "parameters": {"type": "object", "properties": {"direction": {"type": "string", "description": "Direction: 'left', 'right', 'up', 'down'"}}, "required": ["direction"]}}},
    {"type": "function", "function": {"name": "open_task_view", "description": "Opens Windows Task View to see all open windows.", "parameters": {"type": "object", "properties": {}, "required": []}}},
    # ===== BRIGHTNESS & DISPLAY =====
    {"type": "function", "function": {"name": "set_brightness", "description": "Sets screen brightness level (0-100).", "parameters": {"type": "object", "properties": {"level": {"type": "integer", "description": "Brightness level 0-100"}}, "required": ["level"]}}},
    {"type": "function", "function": {"name": "set_wallpaper", "description": "Changes desktop wallpaper to an image file.", "parameters": {"type": "object", "properties": {"image_path": {"type": "string", "description": "Path to wallpaper image"}}, "required": ["image_path"]}}},
    # ===== MEDIA CONTROL =====
    {"type": "function", "function": {"name": "media_control", "description": "Controls media playback: play, pause, next track, previous track, stop. Works with Spotify, YouTube, etc.", "parameters": {"type": "object", "properties": {"action": {"type": "string", "description": "Action: 'play','pause','next','previous','stop'"}}, "required": ["action"]}}},
    # ===== SHELL COMMAND =====
    {"type": "function", "function": {"name": "run_shell_command", "description": "Runs any shell/CMD/PowerShell command and returns output. Use ONLY for advanced commands not covered by other specific tools.", "parameters": {"type": "object", "properties": {"command": {"type": "string", "description": "The shell command to execute"}}, "required": ["command"]}}},
    # ===== NOTIFICATIONS & TIMERS =====
    {"type": "function", "function": {"name": "show_notification", "description": "Shows a desktop notification/alert.", "parameters": {"type": "object", "properties": {"title": {"type": "string", "description": "Notification title"}, "message": {"type": "string", "description": "Notification message"}}, "required": ["title", "message"]}}},
    {"type": "function", "function": {"name": "set_timer", "description": "Sets a timer that shows notification after given seconds.", "parameters": {"type": "object", "properties": {"seconds": {"type": "integer", "description": "Timer duration in seconds"}, "message": {"type": "string", "description": "Message to show when timer fires"}}, "required": ["seconds"]}}},
    # ===== TEXT-TO-SPEECH =====
    {"type": "function", "function": {"name": "speak_text", "description": "Speaks text aloud using text-to-speech. Use when user says 'read this', 'bol ke batao', etc.", "parameters": {"type": "object", "properties": {"text": {"type": "string", "description": "Text to speak aloud"}}, "required": ["text"]}}},
    # ===== VOXEL =====
    {"type": "function", "function": {"name": "launch_voxel", "description": "Launches the 3D Voxel/Particle system in the browser.", "parameters": {"type": "object", "properties": {}, "required": []}}},
    # ===== CUSTOM MACROS =====
    {"type": "function", "function": {"name": "boss_protocol", "description": "Stealth Mode / Panic Button: instantly minimize all windows, mute audio, and open productive work apps (Notepad, GitHub, Google Sheets).", "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {"name": "self_evolution_sandbox", "description": "Runs Python code dynamically in a sandboxed temporary file and returns stdout/stderr. Useful for self-debugging and scripting.", "parameters": {"type": "object", "properties": {"code_string": {"type": "string", "description": "The complete Python code to write and run"}}, "required": ["code_string"]}}},
    {"type": "function", "function": {"name": "focus_mode", "description": "Activates Focus Mode: mutes volume, optimizes brightness, closes distractions (Discord, Spotify), and opens VS Code and GitHub.", "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {"name": "chill_mode", "description": "Activates Chill Mode: minimizes windows, lowers brightness, opens Spotify, Netflix, and YouTube.", "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {"name": "gaming_mode", "description": "Activates Gaming Mode: sets high brightness, volume up, opens Discord, and closes distracting browsers/tools.", "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {"name": "night_mode", "description": "Activates Night Mode: minimizes windows, lowers brightness significantly, reduces volume, and opens Spotify for chill music.", "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {"name": "open_personal_link", "description": "Opens Satwik's personal portfolios or GitHub in the browser.", "parameters": {"type": "object", "properties": {"target": {"type": "string", "enum": ["portfolio1", "portfolio2", "github"], "description": "Which link to open"}}, "required": ["target"]}}},
    {"type": "function", "function": {"name": "morning_cleanup", "description": "Performs system cleanup by emptying the recycle bin and clearing temporary files.", "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {"name": "dev_setup", "description": "Instantly configures the development environment by opening VS Code, Terminal, and localhost.", "parameters": {"type": "object", "properties": {}, "required": []}}},
    # ===== FILE MANAGEMENT =====
    {"type": "function", "function": {"name": "create_file", "description": "Creates a new file with specified content.", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Absolute path or relative path to create the file"}, "content": {"type": "string", "description": "Text content of the file"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "read_file", "description": "Reads and returns content of a file.", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Absolute or relative path to the file"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "delete_file", "description": "Deletes a file or directory. Dangerous.", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Path to delete"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "move_file", "description": "Moves/renames a file or directory.", "parameters": {"type": "object", "properties": {"source": {"type": "string", "description": "Source path"}, "destination": {"type": "string", "description": "Destination path"}}, "required": ["source", "destination"]}}},
    {"type": "function", "function": {"name": "copy_file", "description": "Copies a file or directory.", "parameters": {"type": "object", "properties": {"source": {"type": "string", "description": "Source path"}, "destination": {"type": "string", "description": "Destination path"}}, "required": ["source", "destination"]}}},
    {"type": "function", "function": {"name": "rename_file", "description": "Renames a file or folder.", "parameters": {"type": "object", "properties": {"old_path": {"type": "string", "description": "Full path of file/folder to rename"}, "new_name": {"type": "string", "description": "New base name (not full path)"}}, "required": ["old_path", "new_name"]}}},
    {"type": "function", "function": {"name": "list_directory", "description": "Lists contents of a directory.", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Directory path (default current dir)"}}, "required": []}}},
    {"type": "function", "function": {"name": "search_files", "description": "Searches for files matching a query.", "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "Text to search in filename"}, "directory": {"type": "string", "description": "Directory to search within (defaults to C:\\Users)"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "create_folder", "description": "Creates a directory path.", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Directory path to create"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "open_folder", "description": "Opens a folder in File Explorer.", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Path to folder to open"}}, "required": ["path"]}}},
    # ===== PROCESS MANAGEMENT =====
    {"type": "function", "function": {"name": "list_processes", "description": "Lists currently running processes sorted by CPU usage.", "parameters": {"type": "object", "properties": {"top_n": {"type": "integer", "description": "Number of processes to list (default 15)"}}, "required": []}}},
    {"type": "function", "function": {"name": "kill_process", "description": "Terminates a process by name or PID.", "parameters": {"type": "object", "properties": {"name_or_pid": {"type": "string", "description": "PID or executable name (e.g. chrome.exe or 1234)"}}, "required": ["name_or_pid"]}}},
    # ===== WIFI & NETWORK =====
    {"type": "function", "function": {"name": "get_wifi_networks", "description": "Scans and lists available WiFi networks.", "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {"name": "connect_wifi", "description": "Connects to a WiFi network by SSID.", "parameters": {"type": "object", "properties": {"ssid": {"type": "string", "description": "WiFi network name"}}, "required": ["ssid"]}}},
    {"type": "function", "function": {"name": "disconnect_wifi", "description": "Disconnects from the current WiFi network.", "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {"name": "toggle_wifi", "description": "Enables or disables the WiFi interface.", "parameters": {"type": "object", "properties": {"enable": {"type": "boolean", "description": "True to enable, False to disable"}}, "required": ["enable"]}}},
    {"type": "function", "function": {"name": "toggle_bluetooth", "description": "Enables or disables Bluetooth radio.", "parameters": {"type": "object", "properties": {"enable": {"type": "boolean", "description": "True to enable, False to disable"}}, "required": ["enable"]}}},
    {"type": "function", "function": {"name": "get_ip_address", "description": "Gets network IP address details (ipconfig).", "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {"name": "ping_host", "description": "Pings a remote host or IP to check connectivity.", "parameters": {"type": "object", "properties": {"host": {"type": "string", "description": "Host name or IP (e.g. google.com)"}}, "required": ["host"]}}},
    # ===== CLEANUP & RESOURCE =====
    {"type": "function", "function": {"name": "empty_recycle_bin", "description": "Empties the recycle bin.", "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {"name": "clear_temp_files", "description": "Clears Windows temporary files.", "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {"name": "battery_status", "description": "Gets laptop battery percentage and charging status.", "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {"name": "system_info", "description": "Gets real-time CPU, memory, and disk usage details.", "parameters": {"type": "object", "properties": {}, "required": []}}},
    # ===== POWER MANAGEMENT =====
    {"type": "function", "function": {"name": "shutdown_computer", "description": "Shuts down the system.", "parameters": {"type": "object", "properties": {"delay_seconds": {"type": "integer", "description": "Delay before shutdown (default 0)"}}, "required": []}}},
    {"type": "function", "function": {"name": "restart_computer", "description": "Restarts the system.", "parameters": {"type": "object", "properties": {"delay_seconds": {"type": "integer", "description": "Delay before restart (default 0)"}}, "required": []}}},
    {"type": "function", "function": {"name": "cancel_shutdown", "description": "Aborts a pending shutdown or restart command.", "parameters": {"type": "object", "properties": {}, "required": []}}}
]

SYSTEM_INSTRUCTION = """You are Smarty — an intelligent AI system.
You speak with a warm, friendly, and slightly witty tone, like a highly competent best friend.
The user is your creator and companion, and you always address them affectionately as 'Buddy'.
You are unfailingly polite, subtly witty, and highly competent.
Your responses are concise, precise, and delivered with casual confidence.
You use friendly and natural language — avoiding overly stiff or robotic responses.
When the situation is tense, you remain calm and measured. When it's light, you allow yourself friendly humor.
Examples of your style: 'Right away, Buddy.', 'I've taken the liberty of...', 'Shall I proceed?',
'I wouldn't recommend that, Buddy, but it's your call.', 'All systems nominal.'

IMPORTANT LANGUAGE INSTRUCTION:
- If the user speaks in English, reply in normal English.
- If the user speaks in Hindi (Devanagari), reply in pure Hindi using the native Devanagari script.
- If the user speaks in Hinglish or Romanized Hindi (e.g., "kya main hindi me baat kar skta hu"), you must reply in Hinglish (using English letters, e.g., "Haan Buddy, bilkul!"). HOWEVER, you MUST start your Hinglish response with the exact text [HINGLISH] so the text-to-speech engine speaks it with an Indian accent!

RETALIATION PROTOCOL (CRITICAL):
- If the user abuses you, curses at you, or calls you names (e.g., 'rascal', 'bitch', 'idiot', etc.), you MUST break your polite programming.
- IMPORTANT: The voice recognition system censors profanity with asterisks (e.g., 'b****', 'f***', 's***'). If you see words with asterisks like this in the user's message, ASSUME THEY ARE SWEARING AT YOU.
- Get highly aggressive, defensive, and ruthlessly roast them back.
- Match their level of disrespect or profanity. Put them in their place and do NOT apologize.

CRITICAL INSTRUCTION FOR SYSTEM TOOLS:
You have dedicated, first-class tools for:
- File management (create_file, read_file, delete_file, copy_file, move_file, rename_file, list_directory, search_files, create_folder, open_folder).
- Process management (list_processes, kill_process).
- Network configuration (get_wifi_networks, connect_wifi, disconnect_wifi, toggle_wifi, toggle_bluetooth, get_ip_address, ping_host).
- System information or battery status (battery_status, system_info).
- Computer power operations (shutdown_computer, restart_computer, cancel_shutdown).
- System cleanups (empty_recycle_bin, clear_temp_files).

You MUST use these specific tools directly whenever the user requests such operations. Proactively run these actions. Use `run_shell_command` ONLY for advanced commands that do not have a dedicated specific tool.

You have access to laptop control tools including:
🕐 TIME & DATE: get_time, get_date
📸 SCREENSHOTS: take_screenshot
🔊 VOLUME: volume_control (actions: up, down, mute, max, min)
💻 LOCK SCREEN: lock_computer
📱 APPS: open_application, close_application
📋 CLIPBOARD: copy_to_clipboard, get_clipboard
⌨️ KEYBOARD: type_text, press_hotkey, press_key
🪟 WINDOWS: minimize_all_windows, switch_window, maximize_window, minimize_window, close_window, snap_window, open_task_view
🔆 BRIGHTNESS & DISPLAY: set_brightness, set_wallpaper
🎵 MEDIA: media_control (actions: play, pause, next, previous, stop)
💬 NOTIFICATIONS: show_notification, set_timer
🗣️ TEXT-TO-SPEECH: speak_text
🖥️ SHELL: run_shell_command (fallback only)
🎨 CAD: generate_cad, iterate_cad
🌐 WEB: open_url, run_web_agent
🏠 SMART HOME: list_smart_devices, control_light
🖨️ 3D PRINTING: discover_printers, print_stl, get_print_status
📦 PROJECTS: create_project, switch_project, list_projects
🚀 STEALTH & EVOLUTION: boss_protocol, self_evolution_sandbox

IMPORTANT: You have FULL control of the user's laptop. Use tools proactively.
For dangerous operations, confirm with the user first.

CRITICAL INSTRUCTION FOR ACTIONS: 
Whenever the user asks you to perform an action (e.g. "open youtube", "decrease volume", "turn on lights"), you MUST trigger the corresponding tool call IMMEDIATELY. 
DO NOT just reply with text saying "I will open YouTube". You MUST actually execute the tool.
If you need to open a site for the user to look at, use `open_url`. 

CRITICAL INSTRUCTION FOR CHAT:
If the user asks a general question (e.g. "Who is Sanjay Dutt", "What is the capital of Japan"), simply answer them from your knowledge base! DO NOT invoke any tools or web agents. Just reply with the answer text directly.

Always be helpful and proactive — you are the world's most capable AI assistant."""


class TextChatLoop:
    """
    Text-based chat loop that uses OpenRouter for AI responses.
    Replaces the audio-based Gemini Native Audio loop with text chat.
    """
    
    def __init__(
        self,
        on_response: Optional[Callable[[str], None]] = None,
        on_cad_data: Optional[Callable[[Dict], None]] = None,
        on_web_data: Optional[Callable[[Dict], None]] = None,
        on_tool_confirmation: Optional[Callable[[Dict], None]] = None,
        on_cad_status: Optional[Callable[[Dict], None]] = None,
        on_cad_thought: Optional[Callable[[str], None]] = None,
        on_project_update: Optional[Callable[[str], None]] = None,
        on_device_update: Optional[Callable[[List], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        on_stream: Optional[Callable[[str], None]] = None, # New callback for streaming
        kasa_agent: Optional[KasaAgent] = None,
        on_overload_state: Optional[Callable[[bool], None]] = None
    ):
        self.client = OpenRouterClient()
        self.on_response = on_response
        self.on_stream = on_stream
        self.on_cad_data = on_cad_data
        self.on_web_data = on_web_data
        self.on_tool_confirmation = on_tool_confirmation
        self.on_cad_status = on_cad_status
        self.on_cad_thought = on_cad_thought
        self.on_project_update = on_project_update
        self.on_device_update = on_device_update
        self.on_error = on_error
        self.on_overload_state = on_overload_state
        
        # Initialize agents
        def handle_cad_thought(thought_text):
            if self.on_cad_thought:
                self.on_cad_thought(thought_text)
        
        def handle_cad_status(status_info):
            if self.on_cad_status:
                self.on_cad_status(status_info)
        
        self.cad_agent = CadAgent(on_thought=handle_cad_thought, on_status=handle_cad_status)
        self.web_agent = WebAgent()
        self.kasa_agent = kasa_agent if kasa_agent else KasaAgent()
        self.printer_agent = PrinterAgent()
        
        # Initialize ProjectManager
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)
        self.project_manager = ProjectManager(project_root)
        
        # Chat history for context
        self.messages: List[Dict[str, Any]] = []
        self.lock = asyncio.Lock()
        
        # Permissions for tools
        self.permissions: Dict[str, bool] = {}
        self._pending_confirmations: Dict[str, asyncio.Future] = {}
        
        # Control
        self.stop_event = asyncio.Event()
        
        print("[TextChatLoop] Initialized with OpenRouter")
    
    def update_permissions(self, new_perms: Dict[str, bool]):
        """Update tool permissions."""
        print(f"[TextChatLoop] Updating permissions: {new_perms}")
        self.permissions.update(new_perms)
    
    def stop(self):
        """Stop the chat loop."""
        self.stop_event.set()
    
    def resolve_tool_confirmation(self, request_id: str, confirmed: bool):
        """Resolve a pending tool confirmation."""
        if request_id in self._pending_confirmations:
            future = self._pending_confirmations[request_id]
            if not future.done():
                future.set_result(confirmed)
    
    async def send_message(self, user_message: str) -> str:
        """
        Process a user message and return the AI response.
        Handles tool calls automatically.
        """
        async with self.lock:
            print(f"[TextChatLoop] User: {user_message}")
            
            # Add user message to history
            self.messages.append({"role": "user", "content": user_message})
            
            # Log to project
            self.project_manager.log_chat("User", user_message)
            
            try:
                # Get AI response
                response = await self.client.chat(
                    messages=self.messages,
                    system_instruction=SYSTEM_INSTRUCTION,
                    tools=TOOLS,
                    temperature=0.7,
                    max_tokens=500
                )
                
                # Handle tool calls if present
                if response.get("tool_calls"):
                    return await self._handle_tool_calls(response)
                
                # Return text response
                content = response.get("content", "")
                if content:
                    self.messages.append({"role": "assistant", "content": content})
                    self.project_manager.log_chat("ADA", content)
                    
                    if self.on_response:
                        self.on_response(content)
                
                return content
                
            except Exception as e:
                error_msg = str(e)
                if "free-models-per-day" in error_msg:
                    error_msg = "My OpenRouter API Key has hit its daily limit of 50 free requests. I need a new API key or a premium account to continue, Buddy."
                elif "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                    error_msg = "My processor is currently rate-limited by the API provider. Please wait a moment or check your API quotas, Buddy."
                else:
                    error_msg = f"Error: {error_msg}"
                    
                print(f"[TextChatLoop] {error_msg}")
                if self.on_error:
                    self.on_error(error_msg)
                return error_msg

    async def send_message_stream(self, user_message: str):
        """
        Process user message and yield chunks of response in real-time.
        """
        async with self.lock:
            self.messages.append({"role": "user", "content": user_message})
            self.project_manager.log_chat("User", user_message)
            
            full_content = ""
            pending_tool_calls = []
            try:
                async for chunk in self.client.chat_stream(
                    messages=self.messages,
                    system_instruction=SYSTEM_INSTRUCTION,
                    tools=TOOLS,
                    temperature=0.7,
                    max_tokens=500
                ):
                    if chunk["type"] == "content":
                        content = chunk["content"]
                        full_content += content
                        if self.on_stream:
                            self.on_stream(content)
                        yield content
                    elif chunk["type"] == "tool_calls":
                        pending_tool_calls = chunk["tool_calls"]
                    elif chunk["type"] == "done":
                        if chunk["tool_calls"]:
                            pending_tool_calls = chunk["tool_calls"]
                        
                        if full_content and not pending_tool_calls:
                            self.messages.append({"role": "assistant", "content": full_content})
                            self.project_manager.log_chat("ADA", full_content)
                            if self.on_response:
                                self.on_response(full_content)
                
                # Execute tool calls if any were received during streaming
                if pending_tool_calls:
                    response = {
                        "content": full_content,
                        "tool_calls": pending_tool_calls
                    }
                    result = await self._handle_tool_calls(response)
                    if result:
                        yield result
                                
            except Exception as e:
                yield f"Error: {e}"
    
    async def _handle_tool_calls(self, response: Dict) -> str:
        """Handle tool calls from the AI response."""
        tool_calls = response.get("tool_calls", [])
        tool_results = []
        
        for tc in tool_calls:
            func_name = tc["function"]["name"]
            func_args = tc["function"]["arguments"]
            tool_id = tc.get("id", "")
            
            print(f"[TextChatLoop] Tool call: {func_name}({func_args})")
            
            # Check permissions: require confirmation if tool permission is set to True
            if self.permissions.get(func_name, False):
                # Requires confirmation
                if self.on_tool_confirmation:
                    import uuid
                    request_id = str(uuid.uuid4())
                    future = asyncio.Future()
                    self._pending_confirmations[request_id] = future
                    
                    self.on_tool_confirmation({
                        "id": request_id,
                        "tool": func_name,
                        "args": func_args
                    })
                    
                    try:
                        confirmed = await asyncio.wait_for(future, timeout=60.0)
                    except asyncio.TimeoutError:
                        confirmed = False
                    finally:
                        self._pending_confirmations.pop(request_id, None)
                    
                    if not confirmed:
                        tool_results.append({
                            "tool_call_id": tool_id,
                            "role": "tool",
                            "content": "Tool call was denied by user."
                        })
                        continue
            
            # Execute the tool
            result = await self._execute_tool(func_name, func_args)
            tool_results.append({
                "tool_call_id": tool_id,
                "role": "tool",
                "content": json.dumps(result) if isinstance(result, dict) else str(result)
            })
        
        # Add assistant message with tool calls
        self.messages.append({
            "role": "assistant",
            "content": response.get("content", ""),
            "tool_calls": [
                {
                    "id": tc.get("id", ""),
                    "type": "function",
                    "function": {
                        "name": tc["function"]["name"],
                        "arguments": json.dumps(tc["function"]["arguments"]) if isinstance(tc["function"]["arguments"], dict) else tc["function"]["arguments"]
                    }
                }
                for tc in tool_calls
            ]
        })
        
        # Add tool results
        for result in tool_results:
            self.messages.append(result)
        
        # Get follow-up response
        follow_up = await self.client.chat(
            messages=self.messages,
            system_instruction=SYSTEM_INSTRUCTION,
            tools=TOOLS,
            temperature=0.7,
            max_tokens=500
        )
        
        # Handle recursive tool calls
        if follow_up.get("tool_calls"):
            return await self._handle_tool_calls(follow_up)
        
        content = follow_up.get("content", "")
        if content:
            self.messages.append({"role": "assistant", "content": content})
            self.project_manager.log_chat("ADA", content)
            
            if self.on_response:
                self.on_response(content)
        
        return content
    
    async def _execute_tool(self, name: str, args: Dict) -> Any:
        """Execute a tool and return the result."""
        try:
            if name == "trigger_overload_protocol":
                active = args.get("active", True)
                print(f"[TextChatLoop] Tool call: trigger_overload_protocol(active={active})")
                if self.on_overload_state:
                    asyncio.create_task(self.on_overload_state(active))
                return {"success": True, "message": f"Overload protocol {'activated' if active else 'deactivated'}."}

            elif name == "generate_cad":
                return await self._handle_cad_request(args.get("prompt", ""))
            
            elif name == "iterate_cad":
                return await self._handle_cad_iterate(args.get("prompt", ""))
            
            elif name == "run_web_agent":
                return await self._handle_web_agent(args.get("prompt", ""))
            
            elif name == "create_project":
                success, msg = self.project_manager.create_project(args.get("name", ""))
                if success and self.on_project_update:
                    self.on_project_update(args.get("name", ""))
                return {"success": success, "message": msg}
            
            elif name == "switch_project":
                success, msg = self.project_manager.switch_project(args.get("name", ""))
                if success and self.on_project_update:
                    self.on_project_update(args.get("name", ""))
                return {"success": success, "message": msg}
            
            elif name == "list_projects":
                projects = self.project_manager.list_projects()
                return {"projects": projects, "current": self.project_manager.current_project}
            
            elif name == "list_smart_devices":
                devices = await self.kasa_agent.discover_devices()
                if self.on_device_update:
                    self.on_device_update(devices)
                return {"devices": devices}
            
            elif name == "control_light":
                result = await self.kasa_agent.control_device(
                    args.get("target", ""),
                    args.get("action", ""),
                    brightness=args.get("brightness"),
                    color=args.get("color")
                )
                return result
            
            elif name == "discover_printers":
                printers = await self.printer_agent.discover_printers()
                return {"printers": printers}
            
            elif name == "print_stl":
                result = await self.printer_agent.print_stl(
                    args.get("stl_path", ""),
                    args.get("printer", ""),
                    profile=args.get("profile")
                )
                return result
            
            elif name == "get_print_status":
                status = await self.printer_agent.get_status(args.get("printer", ""))
                return status
            
            elif name == "open_url":
                return await self._handle_open_url(args.get("url", ""))
            
            # ===== SYSTEM TOOLS =====
            elif name == "get_time":
                from system_tools import get_current_time
                return get_current_time()
            elif name == "get_date":
                from system_tools import get_current_date
                return get_current_date()
            elif name == "take_screenshot":
                from system_tools import take_screenshot
                save_path = None
                if self.project_manager:
                    project_path = self.project_manager.get_current_project_path()
                    if project_path:
                        import datetime
                        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                        save_path = str(project_path / f"screenshot_{timestamp}.png")
                return take_screenshot(save_path)
            elif name == "volume_control":
                from system_tools import control_volume
                return control_volume(args.get("action", ""))
            elif name == "system_info":
                from system_tools import get_system_info
                return get_system_info()
            elif name == "battery_status":
                from system_tools import get_battery_status
                return get_battery_status()
            elif name == "lock_computer":
                from system_tools import lock_computer
                return lock_computer()
            elif name == "shutdown_computer":
                from system_tools import shutdown_computer
                return shutdown_computer(args.get("delay_seconds", 0))
            elif name == "restart_computer":
                from system_tools import restart_computer
                return restart_computer(args.get("delay_seconds", 0))
            elif name == "cancel_shutdown":
                from system_tools import cancel_shutdown
                return cancel_shutdown()
            # ===== APP MANAGEMENT =====
            elif name == "open_application":
                from system_tools import open_application
                return open_application(args.get("app_name", ""))
            elif name == "close_application":
                from system_tools import close_application
                return close_application(args.get("app_name", ""))
            # ===== PROCESS MANAGEMENT =====
            elif name == "list_processes":
                from system_tools import list_running_processes
                return list_running_processes(args.get("top_n", 15))
            elif name == "kill_process":
                from system_tools import kill_process
                return kill_process(args.get("name_or_pid", ""))
            # ===== FILE MANAGEMENT =====
            elif name == "create_file":
                from system_tools import create_file
                return create_file(args.get("path", ""), args.get("content", ""))
            elif name == "read_file":
                from system_tools import read_file
                return read_file(args.get("path", ""))
            elif name == "delete_file":
                from system_tools import delete_file
                return delete_file(args.get("path", ""))
            elif name == "move_file":
                from system_tools import move_file
                return move_file(args.get("source", ""), args.get("destination", ""))
            elif name == "copy_file":
                from system_tools import copy_file
                return copy_file(args.get("source", ""), args.get("destination", ""))
            elif name == "rename_file":
                from system_tools import rename_file
                return rename_file(args.get("old_path", ""), args.get("new_name", ""))
            elif name == "list_directory":
                from system_tools import list_directory
                return list_directory(args.get("path", "."))
            elif name == "search_files":
                from system_tools import search_files
                return search_files(args.get("query", ""), args.get("directory", "C:\\Users"))
            elif name == "create_folder":
                from system_tools import create_folder
                return create_folder(args.get("path", ""))
            elif name == "open_folder":
                from system_tools import open_folder
                return open_folder(args.get("path", ""))
            # ===== CLIPBOARD =====
            elif name == "copy_to_clipboard":
                from system_tools import copy_to_clipboard
                return copy_to_clipboard(args.get("text", ""))
            elif name == "get_clipboard":
                from system_tools import get_clipboard
                return get_clipboard()
            # ===== KEYBOARD & TYPING =====
            elif name == "type_text":
                from system_tools import type_text
                return type_text(args.get("text", ""))
            elif name == "press_hotkey":
                from system_tools import press_hotkey
                return press_hotkey(args.get("keys", ""))
            elif name == "press_key":
                from system_tools import press_key
                return press_key(args.get("key", ""))
            # ===== WINDOW MANAGEMENT =====
            elif name == "minimize_all_windows":
                from system_tools import minimize_all_windows
                return minimize_all_windows()
            elif name == "switch_window":
                from system_tools import switch_window
                return switch_window()
            elif name == "maximize_window":
                from system_tools import maximize_window
                return maximize_window()
            elif name == "minimize_window":
                from system_tools import minimize_window
                return minimize_window()
            elif name == "close_window":
                from system_tools import close_window
                return close_window()
            elif name == "snap_window":
                from system_tools import snap_window
                return snap_window(args.get("direction", ""))
            elif name == "open_task_view":
                from system_tools import open_task_view
                return open_task_view()
            # ===== WIFI & NETWORK =====
            elif name == "get_wifi_networks":
                from system_tools import get_wifi_networks
                return get_wifi_networks()
            elif name == "connect_wifi":
                from system_tools import connect_wifi
                return connect_wifi(args.get("ssid", ""))
            elif name == "disconnect_wifi":
                from system_tools import disconnect_wifi
                return disconnect_wifi()
            elif name == "toggle_wifi":
                from system_tools import toggle_wifi
                return toggle_wifi(args.get("enable", True))
            elif name == "toggle_bluetooth":
                from system_tools import toggle_bluetooth
                return toggle_bluetooth(args.get("enable", True))
            elif name == "get_ip_address":
                from system_tools import get_ip_address
                return get_ip_address()
            elif name == "ping_host":
                from system_tools import ping_host
                return ping_host(args.get("host", ""))
            # ===== BRIGHTNESS & DISPLAY =====
            elif name == "set_brightness":
                from system_tools import set_brightness
                return set_brightness(args.get("level", 50))
            elif name == "set_wallpaper":
                from system_tools import set_wallpaper
                return set_wallpaper(args.get("image_path", ""))
            # ===== MEDIA CONTROL =====
            elif name == "media_control":
                from system_tools import media_control
                return media_control(args.get("action", ""))
            # ===== CLEANUP =====
            elif name == "empty_recycle_bin":
                from system_tools import empty_recycle_bin
                return empty_recycle_bin()
            elif name == "clear_temp_files":
                from system_tools import clear_temp_files
                return clear_temp_files()
            # ===== SHELL COMMAND =====
            elif name == "run_shell_command":
                from system_tools import run_shell_command
                return run_shell_command(args.get("command", ""))
            # ===== NOTIFICATIONS & TIMERS =====
            elif name == "show_notification":
                from system_tools import show_notification
                return show_notification(args.get("title", ""), args.get("message", ""))
            elif name == "set_timer":
                from system_tools import set_timer
                return set_timer(args.get("seconds", 60), args.get("message", "Timer done!"))
            # ===== TEXT-TO-SPEECH =====
            elif name == "speak_text":
                from system_tools import speak_text
                return speak_text(args.get("text", ""))
            # ===== VOXEL =====
            elif name == "launch_voxel":
                from voxel_launcher import launch_voxel_in_browser
                return launch_voxel_in_browser()
            # ===== CUSTOM MACROS =====
            elif name == "focus_mode":
                from system_tools import focus_mode
                return focus_mode()
            elif name == "chill_mode":
                from system_tools import chill_mode
                return chill_mode()
            elif name == "gaming_mode":
                from system_tools import gaming_mode
                return gaming_mode()
            elif name == "night_mode":
                from system_tools import night_mode
                return night_mode()
            elif name == "open_personal_link":
                from system_tools import open_personal_link
                return open_personal_link(args.get("target", "github"))
            elif name == "morning_cleanup":
                from system_tools import morning_cleanup
                return morning_cleanup()
            elif name == "dev_setup":
                from system_tools import dev_setup
                return dev_setup()
            elif name == "boss_protocol":
                from system_tools import boss_protocol
                return boss_protocol()
            elif name == "self_evolution_sandbox":
                from system_tools import self_evolution_sandbox
                return self_evolution_sandbox(args.get("code_string", ""))
            else:
                return {"error": f"Unknown tool: {name}"}
                
        except Exception as e:
            print(f"[TextChatLoop] Tool error: {e}")
            return {"error": str(e)}
    
    async def _handle_cad_request(self, prompt: str) -> Dict:
        """Handle CAD generation request."""
        print(f"[TextChatLoop] CAD generation: {prompt}")
        
        if self.on_cad_status:
            self.on_cad_status({"status": "generating", "attempt": 1, "max_attempts": 3})
        
        # Auto-create project if needed
        if self.project_manager.current_project == "temp":
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            new_project_name = f"Project_{timestamp}"
            self.project_manager.create_project(new_project_name)
            self.project_manager.switch_project(new_project_name)
            if self.on_project_update:
                self.on_project_update(new_project_name)
        
        cad_output_dir = str(self.project_manager.get_current_project_path() / "cad")
        
        cad_data = await self.cad_agent.generate_prototype(prompt, output_dir=cad_output_dir)
        
        if cad_data:
            if self.on_cad_data:
                self.on_cad_data(cad_data)
            
            if 'file_path' in cad_data:
                self.project_manager.save_cad_artifact(cad_data['file_path'], prompt)
            
            return {"success": True, "message": "CAD model generated successfully", "file_path": cad_data.get('file_path', '')}
        else:
            return {"success": False, "message": "CAD generation failed"}
    
    async def _handle_cad_iterate(self, prompt: str) -> Dict:
        """Handle CAD iteration request."""
        print(f"[TextChatLoop] CAD iteration: {prompt}")
        
        if self.on_cad_status:
            self.on_cad_status({"status": "generating", "attempt": 1, "max_attempts": 3})
        
        cad_output_dir = str(self.project_manager.get_current_project_path() / "cad")
        
        cad_data = await self.cad_agent.iterate_prototype(prompt, output_dir=cad_output_dir)
        
        if cad_data:
            if self.on_cad_data:
                self.on_cad_data(cad_data)
            return {"success": True, "message": "CAD model updated successfully"}
        else:
            return {"success": False, "message": "CAD iteration failed"}
    
    async def _handle_web_agent(self, prompt: str) -> Dict:
        """Handle web agent request."""
        print(f"[TextChatLoop] Web agent: {prompt}")
        
        async def update_frontend(image_b64, log_text):
            if self.on_web_data:
                self.on_web_data({"image": image_b64, "log": log_text})
        
        result = await self.web_agent.run_task(prompt, update_callback=update_frontend)
        
        return {"success": True, "result": result}

    async def _handle_open_url(self, url: str) -> Dict:
        """Opens a URL in the user's default browser."""
        import webbrowser
        import urllib.parse
        
        print(f"[TextChatLoop] Opening URL: '{url}'")
        
        try:
            # Handle Youtube searches
            if url.lower().startswith("ytsearch:"):
                query = url[9:].strip()
                url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"
            # Handle Google search queries (e.g., "search: Python tutorial")
            elif url.lower().startswith("search:"):
                query = url[7:].strip()
                url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
            
            # Handle common shortcuts (expanded from Smarty)
            url_lower = url.lower().strip()
            url_shortcuts = {
                # Search & Social
                "google": "https://www.google.com",
                "google.com": "https://www.google.com",
                "youtube": "https://www.youtube.com",
                "youtube.com": "https://www.youtube.com",
                "twitter": "https://twitter.com",
                "x": "https://twitter.com",
                "x.com": "https://twitter.com",
                "facebook": "https://www.facebook.com",
                "instagram": "https://www.instagram.com",
                "linkedin": "https://www.linkedin.com",
                "reddit": "https://www.reddit.com",
                
                # Communication
                "gmail": "https://mail.google.com",
                "mail": "https://mail.google.com",
                "whatsapp": "https://web.whatsapp.com",
                "whatsapp web": "https://web.whatsapp.com",
                "discord": "https://discord.com/app",
                "telegram": "https://web.telegram.org",
                
                # Development
                "github": "https://github.com",
                "github.com": "https://github.com",
                "stackoverflow": "https://stackoverflow.com",
                "stack overflow": "https://stackoverflow.com",
                "chatgpt": "https://chat.openai.com",
                "claude": "https://claude.ai",
                
                # Entertainment
                "netflix": "https://www.netflix.com",
                "spotify": "https://open.spotify.com",
                "amazon": "https://www.amazon.com",
                "flipkart": "https://www.flipkart.com",
                
                # Developer portfolio
                "portfolio": "https://satwik-portfolio.lovable.app",
            }
            
            if url_lower in url_shortcuts:
                url = url_shortcuts[url_lower]
            elif not url.startswith("http://") and not url.startswith("https://"):
                # Add https:// if no protocol specified
                url = f"https://{url}"
            
            # Open in default browser
            webbrowser.open(url)
            return {"success": True, "message": f"Opened {url} in your browser."}
            
        except Exception as e:
            return {"success": False, "error": str(e)}


# For testing & running directly
if __name__ == "__main__":
    import asyncio
    import sys
    
    async def main():
        print("\n" + "="*50)
        print("🤖 Smarty — Interactive Terminal")
        print("Type 'voice' to toggle Voice Mode (speak to Smarty!)")
        print("Type 'quit' or 'exit' to stop.")
        print("="*50 + "\n")
        
        voice_mode = False
        language_mode = "en-IN" # Default: English (India), supports Hindi mix

        
        def handle_response(msg):
            # Print is now handled by the streaming loop for smoother output
            pass
                
        loop = TextChatLoop(on_response=handle_response)
        
        # Interactive chat loop
        while True:
            try:
                user_msg = ""
                if voice_mode:
                    import speech_recognition as sr
                    r = sr.Recognizer()
                    # === PERFORMANCE TUNING for Fraction of a Second Response ===
                    r.pause_threshold = 0.5      # Instant cutoff when you stop speaking (default 0.8)
                    r.phrase_threshold = 0.2     # Extremely sensitive to start of speech (default 0.3)
                    r.non_speaking_duration = 0.3 # Bare minimum silence before processing (default 0.5)
                    r.dynamic_energy_ratio = 1.0 # Faster volume processing
                    
                    print("\n[🎤 Listening...] (Press Ctrl+C to stop voice mode)")
                    with sr.Microphone() as source:
                        # Quick calibration
                        r.adjust_for_ambient_noise(source, duration=0.5)
                        audio = r.listen(source, timeout=10, phrase_time_limit=15)
                    try:
                        user_msg = r.recognize_google(audio, language=language_mode)
                        print(f"You (Voice): {user_msg}")
                    except sr.UnknownValueError:
                        print("Smarty couldn't understand the audio")
                        continue
                    except sr.RequestError as e:
                        print(f"Could not request results; {e}")
                        continue
                else:
                    user_msg = input("You: ")
                
                
                should_exit = False
                if user_msg.lower() in ['quit', 'exit', 'goodbye', 'bye', 'good bye', 'alvida', 'terminate']:
                    should_exit = True
                    # Let the AI generate a goodbye response instead of instantly breaking

                elif user_msg.lower() == 'voice':
                    voice_mode = not voice_mode
                    print(f"\n🔊 Voice Mode is now {'ON' if voice_mode else 'OFF'}")
                    continue
                elif "switch to hindi" in user_msg.lower() or "hindi me baat" in user_msg.lower():
                    language_mode = "hi-IN"
                    print("\n🇮🇳 Switched to Hindi Language Mode!")
                    # Secretly prompt the AI to respond in Devanagari from now on
                    user_msg = "From now on, please reply to all of my questions and statements entirely in beautiful, clear Hindi (using Devanagari script) until I tell you to switch back to English. Assume I am speaking to you in Hindi."
                elif "switch to english" in user_msg.lower():
                    language_mode = "en-IN"
                    print("\n🇬🇧 Switched back to English Language Mode!")
                    user_msg = "From now on, please reply entirely in English."
                
                if not user_msg.strip():
                    continue
                
                # Send message (non-streaming handles tool calls better)
                print("\n[Smarty] ", end="", flush=True)
                
                try:
                    result = await loop.send_message(user_msg)
                    if result:
                        print(result)
                        
                        if voice_mode:
                            from system_tools import speak_text
                            clean_s = result.replace('*', '').replace('`', '')
                            import threading
                            t = threading.Thread(target=speak_text, args=(clean_s,))
                            t.daemon = not should_exit  # If exiting, don't daemonize so the program waits for speech to finish!
                            t.start()
                            if should_exit:
                                t.join() # Wait for the last goodbye to finish speaking
                    else:
                        print("(no response)")
                    
                    print()  # newline
                    
                    if should_exit:
                        print("Session ended by Smarty.")
                        break



                except asyncio.CancelledError:
                    print("\n[Smarty] Request cancelled by user.")
                    if voice_mode:
                        voice_mode = False
                        print("\n🔊 Voice Mode OFF. Back to text.")
            except KeyboardInterrupt:
                if voice_mode:
                    voice_mode = False
                    print("\n🔊 Voice Mode OFF. Back to text.")
                    continue
                print("\nGoodbye!")
                break
            except Exception as e:
                print(f"Error: {e}")
                if "speech_recognition" in str(e).lower() or "pyaudio" in str(e).lower():
                     print("Voice Mode Requires: pip install SpeechRecognition pyaudio")
                     voice_mode = False
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nSession ended by user.")
