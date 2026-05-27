import sys
import asyncio

# Fix for asyncio subprocess support on Windows
# MUST BE SET BEFORE OTHER IMPORTS
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import socketio
import engineio.payload
# Prevent "Too many packets in payload" error during HTTP polling startup phase
engineio.payload.Payload.max_decode_packets = 1000

import uvicorn
from fastapi import FastAPI
import asyncio
import threading
import sys
import os
import json
from datetime import datetime
from pathlib import Path



# Ensure we can import smarty
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Force AUDIO_MODE_AVAILABLE to False to use OpenRouter and disable Google Gemini API completely
AUDIO_MODE_AVAILABLE = False
print("[SERVER] Operating in OpenRouter Mode exclusively (Gemini audio mode disabled).")

def get_active_agent(agent_name: str):
    """Dynamically get an agent instance from active audio_loop or text_chat_loop."""
    global audio_loop, text_chat_loop
    if audio_loop and hasattr(audio_loop, agent_name):
        agent = getattr(audio_loop, agent_name)
        if agent is not None:
            return agent
    if text_chat_loop and hasattr(text_chat_loop, agent_name):
        agent = getattr(text_chat_loop, agent_name)
        if agent is not None:
            return agent
    return None

def get_active_project_manager():
    """Dynamically get project manager from active audio_loop or text_chat_loop."""
    global audio_loop, text_chat_loop
    if audio_loop and hasattr(audio_loop, 'project_manager'):
        pm = audio_loop.project_manager
        if pm is not None:
            return pm
    if text_chat_loop and hasattr(text_chat_loop, 'project_manager'):
        pm = text_chat_loop.project_manager
        if pm is not None:
            return pm
    return None

from authenticator import FaceAuthenticator
from kasa_agent import KasaAgent
from text_chat_loop import TextChatLoop
from wake_word_listener import get_wake_word_listener

# Create a Socket.IO server
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
app = FastAPI()
app_socketio = socketio.ASGIApp(sio, app)

import signal

# --- SHUTDOWN HANDLER ---
def signal_handler(sig, frame):
    print(f"\n[SERVER] Caught signal {sig}. Exiting gracefully...")
    # Clean up audio loop
    if audio_loop:
        try:
            print("[SERVER] Stopping Audio Loop...")
            audio_loop.stop() 
        except:
            pass
    # Force kill
    print("[SERVER] Force exiting...")
    os._exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Global state
audio_loop = None
text_chat_loop = None  # OpenRouter text-based chat loop
wake_word_listener = None  # Wake word detection
wake_word_task = None
loop_task = None
authenticator = None
kasa_agent = KasaAgent()
SETTINGS_FILE = "settings.json"

# Global state for voice loop in text chat (OpenRouter) mode
voice_listening_active = False
voice_listener_task = None
is_speaking = False
voice_language_mode = "en-IN"
voice_device_index = None

DEFAULT_SETTINGS = {
    "face_auth_enabled": False, # Default OFF as requested
    "tool_permissions": {
        "generate_cad": False,
        "run_web_agent": False,
        "write_file": False,
        "read_directory": False,
        "read_file": False,
        "create_project": False,
        "switch_project": False,
        "list_projects": False,
        "create_directory": False,
        "list_smart_devices": False,
        "control_light": False,
        "discover_printers": False,
        "print_stl": False,
        "iterate_cad": False
    },
    "printers": [], # List of {host, port, name, type}
    "kasa_devices": [], # List of {ip, alias, model}
    "camera_flipped": False # Invert cursor horizontal direction
}

SETTINGS = DEFAULT_SETTINGS.copy()

def load_settings():
    global SETTINGS
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r') as f:
                loaded = json.load(f)
                # Merge with defaults to ensure new keys exist
                # Deep merge for tool_permissions would be better but shallow merge of top keys + tool_permissions check is okay for now
                for k, v in loaded.items():
                    if k == "tool_permissions" and isinstance(v, dict):
                         SETTINGS["tool_permissions"].update(v)
                    else:
                        SETTINGS[k] = v
            print(f"Loaded settings: {SETTINGS}")
        except Exception as e:
            print(f"Error loading settings: {e}")

def save_settings():
    try:
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(SETTINGS, f, indent=4)
        print("Settings saved.")
    except Exception as e:
        print(f"Error saving settings: {e}")

# Load on startup
load_settings()

def get_settings_payload():
    payload = SETTINGS.copy()
    payload["is_face_registered"] = authenticator.is_registered() if authenticator else False
    payload["face_auth_enabled"] = SETTINGS.get("face_auth_enabled", False)
    return payload

# Initialize face authenticator with socket callbacks
def _create_authenticator():
    """Create a FaceAuthenticator with socket.io callbacks."""
    ref_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reference.jpg")
    
    async def on_auth_status_change(is_authenticated):
        await sio.emit('auth_status', {'authenticated': is_authenticated})
    
    async def on_auth_frame(frame_b64):
        await sio.emit('auth_frame', {'image': frame_b64})
    
    return FaceAuthenticator(
        reference_image_path=ref_path,
        on_status_change=on_auth_status_change,
        on_frame=on_auth_frame
    )

try:
    authenticator = _create_authenticator()
    print(f"[SERVER] Face authenticator initialized. Registered: {authenticator.is_registered()}")
except Exception as e:
    print(f"[SERVER] Face authenticator init failed: {e}")
    authenticator = None

kasa_agent = KasaAgent(known_devices=SETTINGS.get("kasa_devices"))
# tool_permissions is now SETTINGS["tool_permissions"]

def listen_mic_sync(recognizer, mic):
    with mic as source:
        try:
            return recognizer.listen(source, timeout=1.0, phrase_time_limit=15.0)
        except Exception:
            return None

async def voice_listener_loop():
    global voice_listening_active, is_speaking, voice_language_mode, voice_device_index, text_chat_loop
    print(f"[SERVER] Voice listener loop started with device_index={voice_device_index}")
    
    import speech_recognition as sr
    from system_tools import speak_text
    
    recognizer = sr.Recognizer()
    recognizer.pause_threshold = 0.5       # Instant recognition after a brief pause (default 0.8s)
    recognizer.non_speaking_duration = 0.3 # Reduce leading/trailing quiet buffering (default 0.5s)
    recognizer.dynamic_energy_threshold = False
    recognizer.energy_threshold = 300      # Skip background hums for faster turnaround
    try:
        mic = sr.Microphone(device_index=voice_device_index)
    except Exception as e:
        print(f"[VoiceListener] Error creating Microphone with index {voice_device_index}: {e}. Falling back to default.")
        try:
            mic = sr.Microphone()
        except Exception as err:
            print(f"[VoiceListener] Error creating default Microphone: {err}")
            await sio.emit('error', {'msg': 'Failed to initialize microphone.'})
            voice_listening_active = False
            return
    
    try:
        def adjust():
            with mic as source:
                recognizer.adjust_for_ambient_noise(source, duration=1.0)
        await asyncio.to_thread(adjust)
    except Exception as e:
        print(f"[VoiceListener] Error adjusting for ambient noise: {e}")

    while voice_listening_active:
        if is_speaking:
            await asyncio.sleep(0.5)
            continue
            
        audio = await asyncio.to_thread(listen_mic_sync, recognizer, mic)
        
        if audio and voice_listening_active and not is_speaking:
            try:
                def transcribe():
                    return recognizer.recognize_google(audio, language=voice_language_mode)
                
                text = await asyncio.to_thread(transcribe)
                text = text.strip()
                if not text:
                    continue
                
                print(f"[VoiceListener] Transcribed: {text}")
                
                lower_text = text.lower()
                if any(phrase in lower_text for phrase in ["switch to hindi", "hindi mein baat karo", "hindi me baat karo"]):
                    voice_language_mode = "hi-IN"
                    is_speaking = True
                    try:
                        await asyncio.to_thread(speak_text, "अब मैं हिंदी में बात करूँगा, Buddy.", wait=True)
                    finally:
                        is_speaking = False
                    await sio.emit('status', {'msg': 'Language switched to Hindi'})
                    continue
                elif any(phrase in lower_text for phrase in ["switch to english", "english mein baat karo", "english me baat karo"]):
                    voice_language_mode = "en-IN"
                    is_speaking = True
                    try:
                        await asyncio.to_thread(speak_text, "Sure, I will speak in English now, Buddy.", wait=True)
                    finally:
                        is_speaking = False
                    await sio.emit('status', {'msg': 'Language switched to English'})
                    continue
                
                await sio.emit('transcription', {'sender': 'User', 'text': text})
                
                if text_chat_loop:
                    is_speaking = True
                    try:
                        response_text = await text_chat_loop.send_message(text)
                        if response_text:
                            await asyncio.to_thread(speak_text, response_text, wait=True)
                    finally:
                        is_speaking = False
            except sr.UnknownValueError:
                pass
            except sr.RequestError as e:
                print(f"[VoiceListener] Google Speech Recognition service error: {e}")
                await sio.emit('error', {'msg': 'Speech recognition service error.'})
            except Exception as e:
                print(f"[VoiceListener] Error processing audio: {e}")

@app.on_event("startup")
async def startup_event():
    import sys
    print(f"[SERVER DEBUG] Startup Event Triggered")
    print(f"[SERVER DEBUG] Python Version: {sys.version}")
    try:
        loop = asyncio.get_running_loop()
        print(f"[SERVER DEBUG] Running Loop: {type(loop)}")
        policy = asyncio.get_event_loop_policy()
        print(f"[SERVER DEBUG] Current Policy: {type(policy)}")
    except Exception as e:
        print(f"[SERVER DEBUG] Error checking loop: {e}")

    print("[SERVER] Startup: Initializing Kasa Agent...")
    await kasa_agent.initialize()

@app.get("/status")
async def status():
    return {"status": "running", "service": "A.D.A Backend"}

@sio.event
async def connect(sid, environ):
    print(f"Client connected: {sid}")
    await sio.emit('status', {'msg': 'Connected to A.D.A Backend'}, room=sid)
    # Check face auth status
    face_auth_on = SETTINGS.get("face_auth_enabled", False)
    face_registered = authenticator.is_registered() if authenticator else False
    if face_auth_on and face_registered:
        print(f"[SERVER] Face auth enabled & registered. Requiring authentication.")
        await sio.emit('auth_status', {'authenticated': False}, room=sid)
    else:
        await sio.emit('auth_status', {'authenticated': True}, room=sid)
    # Send current settings
    await sio.emit('settings', get_settings_payload(), room=sid)

@sio.event
async def disconnect(sid):
    global voice_listening_active, voice_listener_task
    print(f"Client disconnected: {sid}")
    voice_listening_active = False
    if voice_listener_task:
        voice_listener_task.cancel()
        voice_listener_task = None

@sio.event
async def start_audio(sid, data=None):
    global audio_loop, loop_task
    
    print("Starting Audio Loop...")
    
    device_index = None
    device_name = None
    if data:
        if 'device_index' in data:
            device_index = data['device_index']
        if 'device_name' in data:
            device_name = data['device_name']
            
    print(f"Using input device: Name='{device_name}', Index={device_index}")
    
    if audio_loop:
        if loop_task and (loop_task.done() or loop_task.cancelled()):
             print("Audio loop task appeared finished/cancelled. Clearing and restarting...")
             audio_loop = None
             loop_task = None
        else:
             print("Audio loop already running. Re-connecting client to session.")
             await sio.emit('status', {'msg': 'A.D.A Already Running'})
             return


    # Callback to send audio data to frontend
    def on_audio_data(data_bytes):
        # We need to schedule this on the event loop
        # This is high frequency, so we might want to downsample or batch if it's too much
        asyncio.create_task(sio.emit('audio_data', {'data': list(data_bytes)}))

    # Callback to send CAL data to frontend
    def on_cad_data(data):
        info = f"{len(data.get('vertices', []))} vertices" if 'vertices' in data else f"{len(data.get('data', ''))} bytes (STL)"
        print(f"Sending CAD data to frontend: {info}")
        asyncio.create_task(sio.emit('cad_data', data))

    # Callback to send Browser data to frontend
    def on_web_data(data):
        print(f"Sending Browser data to frontend: {len(data.get('log', ''))} chars logs")
        asyncio.create_task(sio.emit('browser_frame', data))
        
    # Callback to send Transcription data to frontend
    def on_transcription(data):
        # data = {"sender": "User"|"ADA", "text": "..."}
        asyncio.create_task(sio.emit('transcription', data))

    # Callback to send Confirmation Request to frontend
    def on_tool_confirmation(data):
        # data = {"id": "uuid", "tool": "tool_name", "args": {...}}
        print(f"Requesting confirmation for tool: {data.get('tool')}")
        asyncio.create_task(sio.emit('tool_confirmation_request', data))

    # Callback to send CAD status to frontend
    def on_cad_status(status):
        # status can be: 
        # - a string like "generating" (from smarty.py handle_cad_request)
        # - a dict with {status, attempt, max_attempts, error} (from CadAgent)
        if isinstance(status, dict):
            print(f"Sending CAD Status: {status.get('status')} (attempt {status.get('attempt')}/{status.get('max_attempts')})")
            asyncio.create_task(sio.emit('cad_status', status))
        else:
            # Legacy: simple string
            print(f"Sending CAD Status: {status}")
            asyncio.create_task(sio.emit('cad_status', {'status': status}))

    # Callback to send CAD thoughts to frontend (streaming)
    def on_cad_thought(thought_text):
        asyncio.create_task(sio.emit('cad_thought', {'text': thought_text}))

    # Callback to send Project Update to frontend
    def on_project_update(project_name):
        print(f"Sending Project Update: {project_name}")
        asyncio.create_task(sio.emit('project_update', {'project': project_name}))

    # Callback to send Device Update to frontend
    def on_device_update(devices):
        # devices is a list of dicts
        print(f"Sending Kasa Device Update: {len(devices)} devices")
        asyncio.create_task(sio.emit('kasa_devices', devices))

    # Callback to send Error to frontend
    def on_error(msg):
        print(f"Sending Error to frontend: {msg}")
        asyncio.create_task(sio.emit('error', {'msg': msg}))

    # Initialize Smarty
    try:
        print(f"Initializing AudioLoop with device_index={device_index}")
        audio_loop = smarty.AudioLoop(
            video_mode="none", 
            on_audio_data=on_audio_data,
            on_cad_data=on_cad_data,
            on_web_data=on_web_data,
            on_transcription=on_transcription,
            on_tool_confirmation=on_tool_confirmation,
            on_cad_status=on_cad_status,
            on_cad_thought=on_cad_thought,
            on_project_update=on_project_update,
            on_device_update=on_device_update,
            on_error=on_error,

            input_device_index=device_index,
            input_device_name=device_name,
            kasa_agent=kasa_agent,
            on_overload_state=on_overload_state
        )
        print("AudioLoop initialized successfully.")

        # Apply current permissions
        audio_loop.update_permissions(SETTINGS["tool_permissions"])
        
        # Check initial mute state
        if data and data.get('muted', False):
            print("Starting with Audio Paused")
            audio_loop.set_paused(True)

        print("Creating asyncio task for AudioLoop.run()")
        loop_task = asyncio.create_task(audio_loop.run())
        
        # Add a done callback to catch silent failures in the loop
        def handle_loop_exit(task):
            try:
                task.result()
            except asyncio.CancelledError:
                print("Audio Loop Cancelled")
            except Exception as e:
                print(f"Audio Loop Crashed: {e}")
                # You could emit 'error' here if you have context
        
        loop_task.add_done_callback(handle_loop_exit)
        
        print("Emitting 'A.D.A Started'")
        await sio.emit('status', {'msg': 'A.D.A Started'})

        # Load saved printers
        saved_printers = SETTINGS.get("printers", [])
        if saved_printers and audio_loop.printer_agent:
            print(f"[SERVER] Loading {len(saved_printers)} saved printers...")
            for p in saved_printers:
                audio_loop.printer_agent.add_printer_manually(
                    name=p.get("name", p["host"]),
                    host=p["host"],
                    port=p.get("port", 80),
                    printer_type=p.get("type", "moonraker"),
                    camera_url=p.get("camera_url")
                )
        
        # Start Printer Monitor
        asyncio.create_task(monitor_printers_loop())
        
    except Exception as e:
        print(f"CRITICAL ERROR STARTING ADA: {e}")
        import traceback
        traceback.print_exc()
        await sio.emit('error', {'msg': f"Failed to start: {str(e)}"})
        audio_loop = None # Ensure we can try again

@sio.event
async def set_barge_in_prevention(sid, data=None):
    """Enable or disable barge-in prevention (mute mic while ADA speaks)
    
    Args:
        data: dict with 'enabled' (bool) and optional 'threshold' (int, default 2000)
              Lower threshold = more sensitive to interruptions
              Higher threshold = requires louder interruptions
    """
    global audio_loop
    
    if not audio_loop:
        print("[SERVER] [ERROR] Audio loop not running")
        return
    
    try:
        enabled = data.get('enabled', True) if data else True
        threshold = data.get('threshold', 2000) if data else 2000
        
        audio_loop.set_barge_in_prevention(enabled, threshold)
        
        status_msg = f"Barge-in prevention {'enabled' if enabled else 'disabled'} (threshold: {threshold})"
        await sio.emit('status', {'msg': status_msg})
        print(f"[SERVER] {status_msg}")
        
    except Exception as e:
        print(f"[SERVER] [ERROR] Failed to set barge-in prevention: {e}")
        await sio.emit('error', {'msg': f"Failed to update audio settings: {str(e)}"})


overload_active = False

async def flash_kasa_lights_loop():
    global overload_active
    # Flashing colors: Red (0, 100, 100) and Orange (30, 100, 100)
    colors = [(0, 100, 100), (30, 100, 100)]
    
    try:
        # Resolve light IPs
        light_ips = []
        for ip, dev in kasa_agent.devices.items():
            if dev.is_bulb or dev.is_dimmer:
                light_ips.append(ip)
                
        if not light_ips:
            print("[SERVER OVERLOAD] No smart lights detected for overload visual feedback.")
            # Even if no lights, let the countdown run
            from system_tools import speak_text
            await asyncio.to_thread(speak_text, "System core overloaded. Red alert activated. Core temperature at 98 percent. Emergency venting required, Buddy.", wait=True)
            return

        print(f"[SERVER OVERLOAD] Starting Kasa flashing sequence on {len(light_ips)} lights...")
        
        # Run speech countdown
        from system_tools import speak_text
        async def countdown():
            speak_text("System core overloaded. Red alert activated. Core temperature at 98 percent. Emergency venting required, Buddy.", wait=True)
        asyncio.create_task(asyncio.to_thread(countdown))

        step = 0
        while overload_active:
            tasks = []
            current_color = colors[step % len(colors)]
            for ip in light_ips:
                tasks.append(kasa_agent.turn_on(ip))
                tasks.append(kasa_agent.set_color(ip, current_color))
                tasks.append(kasa_agent.set_brightness(ip, 100))
            
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            
            step += 1
            await asyncio.sleep(0.6)
            
        # Restoring lights back to standard warm white
        print("[SERVER OVERLOAD] Restoring lights to normal...")
        restore_tasks = []
        for ip in light_ips:
            restore_tasks.append(kasa_agent.set_color(ip, (30, 20, 80)))
            restore_tasks.append(kasa_agent.set_brightness(ip, 60))
        if restore_tasks:
            await asyncio.gather(*restore_tasks, return_exceptions=True)
            
    except Exception as e:
        print(f"[SERVER OVERLOAD] Exception in light flashing loop: {e}")

async def on_overload_state(active: bool):
    global overload_active
    print(f"[SERVER] Overload State toggled: {active}")
    await sio.emit('overload_state', {'active': active})
    
    if active:
        if not overload_active:
            overload_active = True
            asyncio.create_task(flash_kasa_lights_loop())
    else:
        overload_active = False

async def monitor_printers_loop():
    """Background task to query printer status periodically."""
    print("[SERVER] Starting Printer Monitor Loop")
    while audio_loop and audio_loop.printer_agent:
        try:
            agent = audio_loop.printer_agent
            if not agent.printers:
                await asyncio.sleep(5)
                continue
                
            tasks = []
            for host, printer in agent.printers.items():
                if printer.printer_type.value != "unknown":
                    tasks.append(agent.get_print_status(host))
            
            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for res in results:
                    if isinstance(res, Exception):
                        pass # Ignore errors for now
                    elif res:
                        # res is PrintStatus object
                        await sio.emit('print_status_update', res.to_dict())
                        
        except asyncio.CancelledError:
            print("[SERVER] Printer Monitor Cancelled")
            break
        except Exception as e:
            print(f"[SERVER] Monitor Loop Error: {e}")
            
        await asyncio.sleep(2) # Update every 2 seconds for responsiveness

@sio.event
async def stop_audio(sid):
    global audio_loop
    if audio_loop:
        audio_loop.stop() 
        print("Stopping Audio Loop")
        audio_loop = None
        await sio.emit('status', {'msg': 'A.D.A Stopped'})

@sio.event
async def pause_audio(sid):
    global audio_loop, voice_listening_active, voice_listener_task
    if audio_loop:
        audio_loop.set_paused(True)
        print("Pausing Audio")
        await sio.emit('status', {'msg': 'Audio Paused'})
    else:
        print("Pausing Voice Listening in OpenRouter Mode")
        voice_listening_active = False
        if voice_listener_task:
            voice_listener_task.cancel()
            voice_listener_task = None
        await sio.emit('status', {'msg': 'Voice listening paused'})

@sio.event
async def resume_audio(sid):
    global audio_loop, text_chat_loop, voice_listening_active, voice_listener_task
    if audio_loop:
        audio_loop.set_paused(False)
        print("Resuming Audio")
        await sio.emit('status', {'msg': 'Audio Resumed'})
    elif text_chat_loop:
        print("Resuming Voice Listening in OpenRouter Mode")
        voice_listening_active = True
        if not voice_listener_task or voice_listener_task.done():
            voice_listener_task = asyncio.create_task(voice_listener_loop())
        await sio.emit('status', {'msg': 'Voice listening active'})

@sio.event
async def confirm_tool(sid, data):
    # data: { "id": "...", "confirmed": True/False }
    request_id = data.get('id')
    confirmed = data.get('confirmed', False)
    
    print(f"[SERVER DEBUG] Received confirmation response for {request_id}: {confirmed}")
    
    if text_chat_loop:
        text_chat_loop.resolve_tool_confirmation(request_id, confirmed)
    elif audio_loop:
        audio_loop.resolve_tool_confirmation(request_id, confirmed)
    else:
        print("No active chat loop to resolve confirmation.")

@sio.event
async def shutdown(sid, data=None):
    """Gracefully shutdown the server when the application closes."""
    global audio_loop, loop_task, authenticator, voice_listening_active, voice_listener_task
    
    print("[SERVER] ========================================")
    print("[SERVER] SHUTDOWN SIGNAL RECEIVED FROM FRONTEND")
    print("[SERVER] ========================================")
    
    # Stop voice listening
    voice_listening_active = False
    if voice_listener_task:
        voice_listener_task.cancel()
        voice_listener_task = None
        
    # Stop audio loop
    if audio_loop:
        print("[SERVER] Stopping Audio Loop...")
        audio_loop.stop()
        audio_loop = None
    
    # Cancel the loop task if running
    if loop_task and not loop_task.done():
        print("[SERVER] Cancelling loop task...")
        loop_task.cancel()
        loop_task = None
    
    # Stop authenticator if running
    if authenticator:
        print("[SERVER] Stopping Authenticator...")
        authenticator.stop()
    
    print("[SERVER] Graceful shutdown complete. Terminating process...")
    
    # Force exit immediately - os._exit bypasses cleanup but ensures termination
    os._exit(0)

@sio.event
async def user_input(sid, data):
    """Handle text input - works with both audio loop (Gemini) and text chat loop (OpenRouter)."""
    text = data.get('text')
    print(f"[SERVER DEBUG] User input received: '{text}'")
    
    # Try text chat loop first (OpenRouter mode)
    if text_chat_loop:
        print(f"[SERVER DEBUG] Using TextChatLoop (OpenRouter)")
        try:
            response = await text_chat_loop.send_message(text)
            # Response is already emitted via callbacks
            return
        except Exception as e:
            print(f"[SERVER DEBUG] TextChatLoop error: {e}")
            await sio.emit('error', {'msg': str(e)})
            return
    
    # Fall back to audio loop (Gemini mode)
    if not audio_loop:
        print("[SERVER DEBUG] [Error] No active chat loop. Cannot send text.")
        return

    if not audio_loop.session:
        print("[SERVER DEBUG] [Error] Session is None. Cannot send text.")
        return

    if text:
        print(f"[SERVER DEBUG] Sending message to model via AudioLoop: '{text}'")
        
        # Log User Input to Project History
        if audio_loop and audio_loop.project_manager:
            audio_loop.project_manager.log_chat("User", text)
            
        # INJECT VIDEO FRAME IF AVAILABLE (VAD-style logic for Text Input)
        if audio_loop and audio_loop._latest_image_payload:
            print(f"[SERVER DEBUG] Piggybacking video frame with text input.")
            try:
                await audio_loop.session.send(input=audio_loop._latest_image_payload, end_of_turn=False)
            except Exception as e:
                print(f"[SERVER DEBUG] Failed to send piggyback frame: {e}")
                
        await audio_loop.session.send(input=text, end_of_turn=True)
        print(f"[SERVER DEBUG] Message sent to model successfully.")


@sio.event
async def start_text_chat(sid, data=None):
    """Start text-based chat using OpenRouter (alternative to audio-based Gemini)."""
    global text_chat_loop, voice_device_index, voice_listening_active, voice_listener_task
    
    print("[SERVER] Starting Text Chat Loop (OpenRouter Mode)...")
    
    if text_chat_loop:
        print("[SERVER] Text chat loop already running. Syncing connection state...")
        if data and 'device_index' in data:
            voice_device_index = data['device_index']
            print(f"[SERVER] Updated voice_device_index: {voice_device_index}")
        
        is_muted = data.get('muted', True) if data else True
        if not is_muted:
            print("[SERVER] Voice listening active on reconnect")
            voice_listening_active = True
            if not voice_listener_task or voice_listener_task.done():
                voice_listener_task = asyncio.create_task(voice_listener_loop())
        else:
            print("[SERVER] Voice listening muted on reconnect")
            voice_listening_active = False
            if voice_listener_task:
                voice_listener_task.cancel()
                voice_listener_task = None
                
        # Sync initial project
        if text_chat_loop.project_manager:
            project_name = text_chat_loop.project_manager.current_project
            print(f"Syncing Project Update: {project_name}")
            asyncio.create_task(sio.emit('project_update', {'project': project_name}))
            
        await sio.emit('status', {'msg': 'Text Chat Already Active (OpenRouter Mode)'})
        return
    
    if data and 'device_index' in data:
        voice_device_index = data['device_index']
    
    # Callback functions
    def on_response(content):
        asyncio.create_task(sio.emit('transcription', {'sender': 'ADA', 'text': content}))
    
    def on_cad_data(data):
        info = f"{len(data.get('data', ''))} bytes (STL)" if 'data' in data else "CAD data"
        print(f"Sending CAD data to frontend: {info}")
        asyncio.create_task(sio.emit('cad_data', data))
    
    def on_web_data(data):
        print(f"Sending Browser data to frontend")
        asyncio.create_task(sio.emit('browser_frame', data))
    
    def on_tool_confirmation(data):
        print(f"Requesting confirmation for tool: {data.get('tool')}")
        asyncio.create_task(sio.emit('tool_confirmation_request', data))
    
    def on_cad_status(status):
        if isinstance(status, dict):
            asyncio.create_task(sio.emit('cad_status', status))
        else:
            asyncio.create_task(sio.emit('cad_status', {'status': status}))
    
    def on_cad_thought(thought_text):
        asyncio.create_task(sio.emit('cad_thought', {'text': thought_text}))
    
    def on_project_update(project_name):
        print(f"Sending Project Update: {project_name}")
        asyncio.create_task(sio.emit('project_update', {'project': project_name}))
    
    def on_device_update(devices):
        asyncio.create_task(sio.emit('kasa_devices', devices))
    
    def on_error(msg):
        print(f"Sending Error to frontend: {msg}")
        asyncio.create_task(sio.emit('error', {'msg': msg}))
    
    try:
        text_chat_loop = TextChatLoop(
            on_response=on_response,
            on_cad_data=on_cad_data,
            on_web_data=on_web_data,
            on_tool_confirmation=on_tool_confirmation,
            on_cad_status=on_cad_status,
            on_cad_thought=on_cad_thought,
            on_project_update=on_project_update,
            on_device_update=on_device_update,
            on_error=on_error,
            kasa_agent=kasa_agent,
            on_overload_state=on_overload_state
        )
        
        # Apply permissions
        text_chat_loop.update_permissions(SETTINGS["tool_permissions"])
        
        print("[SERVER] TextChatLoop initialized successfully (OpenRouter Mode)")
        await sio.emit('status', {'msg': 'Text Chat Active (OpenRouter Mode)'})
        
        # Start voice loop if frontend says not muted
        is_muted = data.get('muted', True) if data else True
        if not is_muted:
            print("[SERVER] Starting Text Chat with voice listening active")
            voice_listening_active = True
            voice_listener_task = asyncio.create_task(voice_listener_loop())
            # AI speaks ready-greeting on startup
            try:
                from system_tools import speak_text
                asyncio.create_task(asyncio.to_thread(speak_text, "All systems nominal, Buddy. I am online and ready to control your system.", wait=False))
            except Exception as e:
                print(f"[SERVER] Error speaking ready-greeting: {e}")
        else:
            print("[SERVER] Starting Text Chat with voice listening muted")
            voice_listening_active = False
            
        # Sync initial project
        if text_chat_loop.on_project_update and text_chat_loop.project_manager:
            on_project_update(text_chat_loop.project_manager.current_project)
        
    except Exception as e:
        print(f"[SERVER] Error starting text chat: {e}")
        import traceback
        traceback.print_exc()
        await sio.emit('error', {'msg': f"Failed to start text chat: {str(e)}"})
        text_chat_loop = None


@sio.event
async def stop_text_chat(sid):
    """Stop the text chat loop."""
    global text_chat_loop, voice_listening_active, voice_listener_task
    
    if text_chat_loop:
        text_chat_loop.stop()
        text_chat_loop = None
        print("[SERVER] Text Chat Loop stopped")
        
        # Stop voice listening
        voice_listening_active = False
        if voice_listener_task:
            voice_listener_task.cancel()
            voice_listener_task = None
            
        await sio.emit('status', {'msg': 'Text Chat Stopped'})

import json
from datetime import datetime
from pathlib import Path

# ... (imports)

@sio.event
async def video_frame(sid, data):
    # data should contain 'image' which is binary (blob) or base64 encoded
    image_data = data.get('image')
    if image_data and audio_loop:
        # We don't await this because we don't want to block the socket handler
        # But send_frame is async, so we create a task
        asyncio.create_task(audio_loop.send_frame(image_data))

@sio.event
async def save_memory(sid, data):
    try:
        messages = data.get('messages', [])
        if not messages:
            print("No messages to save.")
            return

        # Ensure directory exists
        memory_dir = Path("long_term_memory")
        memory_dir.mkdir(exist_ok=True)

        # Generate filename
        # Use provided filename if available, else timestamp
        provided_name = data.get('filename')
        
        if provided_name:
            # Simple sanitization
            if not provided_name.endswith('.txt'):
                provided_name += '.txt'
            # Prevent directory traversal
            filename = memory_dir / Path(provided_name).name 
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = memory_dir / f"memory_{timestamp}.txt"

        # Write to file
        with open(filename, 'w', encoding='utf-8') as f:
            for msg in messages:
                sender = msg.get('sender', 'Unknown')
                text = msg.get('text', '')
        print(f"Conversation saved to {filename}")
        await sio.emit('status', {'msg': 'Memory Saved Successfully'})

    except Exception as e:
        print(f"Error saving memory: {e}")
        await sio.emit('error', {'msg': f"Failed to save memory: {str(e)}"})

@sio.event
async def upload_memory(sid, data):
    print(f"Received memory upload request")
    try:
        memory_text = data.get('memory', '')
        if not memory_text:
            print("No memory data provided.")
            return

        if not audio_loop:
             print("[SERVER DEBUG] [Error] Audio loop is None. Cannot load memory.")
             await sio.emit('error', {'msg': "System not ready (Audio Loop inactive)"})
             return
        
        if not audio_loop.session:
             print("[SERVER DEBUG] [Error] Session is None. Cannot load memory.")
             await sio.emit('error', {'msg': "System not ready (No active session)"})
             return

        # Send to model
        print("Sending memory context to model...")
        context_msg = f"System Notification: The user has uploaded a long-term memory file. Please load the following context into your understanding. The format is a text log of previous conversations:\n\n{memory_text}"
        
        await audio_loop.session.send(input=context_msg, end_of_turn=True)
        print("Memory context sent successfully.")
        await sio.emit('status', {'msg': 'Memory Loaded into Context'})

    except Exception as e:
        print(f"Error uploading memory: {e}")
        await sio.emit('error', {'msg': f"Failed to upload memory: {str(e)}"})

@sio.event
async def discover_kasa(sid):
    print(f"Received discover_kasa request")
    try:
        devices = await kasa_agent.discover_devices()
        await sio.emit('kasa_devices', devices)
        await sio.emit('status', {'msg': f"Found {len(devices)} Kasa devices"})
        
        # Save to settings
        # devices is a list of full device info dicts. minimizing for storage.
        saved_devices = []
        for d in devices:
            saved_devices.append({
                "ip": d["ip"],
                "alias": d["alias"],
                "model": d["model"]
            })
        
        # Merge with existing to preserve any manual overrides? 
        # For now, just overwrite with latest scan result + previously known if we want to be fancy,
        # but user asked for "Any new devices that are scanned are added there".
        # A simple full persistence of current state is safest.
        SETTINGS["kasa_devices"] = saved_devices
        save_settings()
        print(f"[SERVER] Saved {len(saved_devices)} Kasa devices to settings.")
        
    except Exception as e:
        print(f"Error discovering kasa: {e}")
        await sio.emit('error', {'msg': f"Kasa Discovery Failed: {str(e)}"})

@sio.event
async def iterate_cad(sid, data):
    # data: { prompt: "make it bigger" }
    prompt = data.get('prompt')
    print(f"Received iterate_cad request: '{prompt}'")
    
    cad_agent = get_active_agent('cad_agent')
    project_manager = get_active_project_manager()
    if not cad_agent or not project_manager:
        await sio.emit('error', {'msg': "CAD Agent or Project Manager not available"})
        return

    try:
        # Notify user work has started
        await sio.emit('status', {'msg': 'Iterating design...'})
        await sio.emit('cad_status', {'status': 'generating'})
        
        # Call the agent with project path
        cad_output_dir = str(project_manager.get_current_project_path() / "cad")
        result = await cad_agent.iterate_prototype(prompt, output_dir=cad_output_dir)
        
        if result:
            info = f"{len(result.get('data', ''))} bytes (STL)"
            print(f"Sending updated CAD data: {info}")
            await sio.emit('cad_data', result)
            # Save to Project
            if 'file_path' in result:
                saved_path = project_manager.save_cad_artifact(result['file_path'], prompt)
                if saved_path:
                    print(f"[SERVER] Saved iterated CAD to {saved_path}")

            await sio.emit('status', {'msg': 'Design updated'})
        else:
            await sio.emit('error', {'msg': 'Failed to update design'})
            
    except Exception as e:
        print(f"Error iterating CAD: {e}")
        await sio.emit('error', {'msg': f"Iteration Error: {str(e)}"})

@sio.event
async def generate_cad(sid, data):
    # data: { prompt: "make a cube" }
    prompt = data.get('prompt')
    print(f"Received generate_cad request: '{prompt}'")
    
    cad_agent = get_active_agent('cad_agent')
    project_manager = get_active_project_manager()
    if not cad_agent or not project_manager:
        await sio.emit('error', {'msg': "CAD Agent or Project Manager not available"})
        return

    try:
        await sio.emit('status', {'msg': 'Generating new design...'})
        await sio.emit('cad_status', {'status': 'generating'})
        
        # Use generate_prototype based on prompt with project path
        cad_output_dir = str(project_manager.get_current_project_path() / "cad")
        result = await cad_agent.generate_prototype(prompt, output_dir=cad_output_dir)
        
        if result:
            info = f"{len(result.get('data', ''))} bytes (STL)"
            print(f"Sending newly generated CAD data: {info}")
            await sio.emit('cad_data', result)

            # Save to Project
            if 'file_path' in result:
                saved_path = project_manager.save_cad_artifact(result['file_path'], prompt)
                if saved_path:
                    print(f"[SERVER] Saved generated CAD to {saved_path}")

            await sio.emit('status', {'msg': 'Design generated'})
        else:
            await sio.emit('error', {'msg': 'Failed to generate design'})
            
    except Exception as e:
        print(f"Error generating CAD: {e}")
        await sio.emit('error', {'msg': f"Generation Error: {str(e)}"})

@sio.event
async def prompt_web_agent(sid, data):
    # data: { prompt: "find xyz" }
    prompt = data.get('prompt')
    print(f"Received web agent prompt: '{prompt}'")
    
    web_agent = get_active_agent('web_agent')
    if not web_agent:
        await sio.emit('error', {'msg': "Web Agent not available"})
        return

    try:
        await sio.emit('status', {'msg': 'Web Agent running...'})
        
        async def update_frontend(image_b64, log_text):
            await sio.emit('browser_frame', {"image": image_b64, "log": log_text})
            
        await web_agent.run_task(prompt, update_callback=update_frontend)
        await sio.emit('status', {'msg': 'Web Agent finished'})
        
    except Exception as e:
        print(f"Error running Web Agent: {e}")
        await sio.emit('error', {'msg': f"Web Agent Error: {str(e)}"})

@sio.event
async def discover_printers(sid):
    print("Received discover_printers request")
    
    printer_agent = get_active_agent('printer_agent')
    if not printer_agent:
        saved_printers = SETTINGS.get("printers", [])
        if saved_printers:
            # Convert saved printers to the expected format
            printer_list = []
            for p in saved_printers:
                printer_list.append({
                    "name": p.get("name", p["host"]),
                    "host": p["host"],
                    "port": p.get("port", 80),
                    "printer_type": p.get("type", "unknown"),
                    "camera_url": p.get("camera_url")
                })
            print(f"[SERVER] Returning {len(printer_list)} saved printers (active agent not ready)")
            await sio.emit('printer_list', printer_list)
            return
        else:
            await sio.emit('printer_list', [])
            await sio.emit('status', {'msg': "Connect to A.D.A to enable printer discovery"})
            return
        
    try:
        printers = await printer_agent.discover_printers()
        await sio.emit('printer_list', printers)
        await sio.emit('status', {'msg': f"Found {len(printers)} printers"})
    except Exception as e:
        print(f"Error discovering printers: {e}")
        await sio.emit('error', {'msg': f"Printer Discovery Failed: {str(e)}"})

@sio.event
async def add_printer(sid, data):
    # data: { host: "192.168.1.50", name: "My Printer", type: "moonraker" }
    raw_host = data.get('host')
    name = data.get('name') or raw_host
    ptype = data.get('type', "moonraker")
    
    # Parse port if present
    if ":" in raw_host:
        host, port_str = raw_host.split(":")
        port = int(port_str)
    else:
        host = raw_host
        port = 80
    
    print(f"Received add_printer request: {host}:{port} ({ptype})")
    
    printer_agent = get_active_agent('printer_agent')
    if not printer_agent:
        await sio.emit('error', {'msg': "Printer Agent not available"})
        return
        
    try:
        # Add manually
        camera_url = data.get('camera_url')
        printer = printer_agent.add_printer_manually(name, host, port=port, printer_type=ptype, camera_url=camera_url)
        
        # Save to settings
        new_printer_config = {
            "name": name,
            "host": host,
            "port": port,
            "type": ptype,
            "camera_url": camera_url
        }
        
        # Check if already exists to avoid duplicates
        exists = False
        for p in SETTINGS.get("printers", []):
            if p["host"] == host and p["port"] == port:
                exists = True
                break
        
        if not exists:
            if "printers" not in SETTINGS:
                SETTINGS["printers"] = []
            SETTINGS["printers"].append(new_printer_config)
            save_settings()
            print(f"[SERVER] Saved printer {name} to settings.")
        
        # Probe to confirm/correct type
        print(f"Probing {host} to confirm type...")
        # Try port 7125 (Moonraker) and 4408 (Fluidd/K1) 
        ports_to_try = [80, 7125, 4408]
        
        actual_type = "unknown"
        for port in ports_to_try:
             found_type = await printer_agent._probe_printer_type(host, port)
             if found_type.value != "unknown":
                 actual_type = found_type
                 # Update port if different
                 if port != 80:
                     printer.port = port
                 break
        
        if actual_type != "unknown" and actual_type != printer.printer_type:
             printer.printer_type = actual_type
             print(f"Corrected type to {actual_type.value} on port {printer.port}")
             
        # Refresh list for everyone
        printers = [p.to_dict() for p in printer_agent.printers.values()]
        await sio.emit('printer_list', printers)
        await sio.emit('status', {'msg': f"Added printer: {name}"})
        
    except Exception as e:
        print(f"Error adding printer: {e}")
        await sio.emit('error', {'msg': f"Failed to add printer: {str(e)}"})

@sio.event
async def print_stl(sid, data):
    print(f"Received print_stl request: {data}")
    # data: { stl_path: "path/to.stl" | "current", printer: "name_or_ip", profile: "optional" }
    
    printer_agent = get_active_agent('printer_agent')
    project_manager = get_active_project_manager()
    if not printer_agent:
        await sio.emit('error', {'msg': "Printer Agent not available"})
        return
        
    try:
        stl_path = data.get('stl_path', 'current')
        printer_name = data.get('printer')
        profile = data.get('profile')
        
        if not printer_name:
             await sio.emit('error', {'msg': "No printer specified"})
             return
             
        await sio.emit('status', {'msg': f"Preparing print for {printer_name}..."})
        
        # Get current project path for resolution
        current_project_path = None
        if project_manager:
            current_project_path = str(project_manager.get_current_project_path())
            print(f"[SERVER DEBUG] Using project path: {current_project_path}")

        # Resolve STL path before slicing so we can preview it
        resolved_stl = printer_agent._resolve_file_path(stl_path, current_project_path)
        
        if resolved_stl and os.path.exists(resolved_stl):
            # Open the STL in the CAD module for preview
            try:
                import base64
                with open(resolved_stl, 'rb') as f:
                    stl_data = f.read()
                stl_b64 = base64.b64encode(stl_data).decode('utf-8')
                stl_filename = os.path.basename(resolved_stl)
                
                print(f"[SERVER] Opening STL in CAD module: {stl_filename}")
                await sio.emit('cad_data', {
                    'format': 'stl',
                    'data': stl_b64,
                    'filename': stl_filename
                })
            except Exception as e:
                print(f"[SERVER] Warning: Could not preview STL: {e}")
        
        # Progress Callback
        async def on_slicing_progress(percent, message):
            await sio.emit('slicing_progress', {
                'printer': printer_name,
                'percent': percent,
                'message': message
            })
            if percent < 100:
                  await sio.emit('status', {'msg': f"Slicing: {percent}%"})

        result = await printer_agent.print_stl(
            stl_path, 
            printer_name, 
            profile,
            progress_callback=on_slicing_progress,
            root_path=current_project_path
        )
        
        await sio.emit('print_result', result)
        await sio.emit('status', {'msg': f"Print Job: {result.get('status', 'unknown')}"})
        
    except Exception as e:
        print(f"Error printing STL: {e}")
        await sio.emit('error', {'msg': f"Print Failed: {str(e)}"})

@sio.event
async def get_slicer_profiles(sid):
    """Get available OrcaSlicer profiles for manual selection."""
    print("Received get_slicer_profiles request")
    printer_agent = get_active_agent('printer_agent')
    if not printer_agent:
        await sio.emit('error', {'msg': "Printer Agent not available"})
        return
    
    try:
        profiles = printer_agent.get_available_profiles()
        await sio.emit('slicer_profiles', profiles)
    except Exception as e:
        print(f"Error getting slicer profiles: {e}")
        await sio.emit('error', {'msg': f"Failed to get profiles: {str(e)}"})

@sio.event
async def control_kasa(sid, data):
    # data: { ip, action: "on"|"off"|"brightness"|"color", value: ... }
    ip = data.get('ip')
    action = data.get('action')
    print(f"Kasa Control: {ip} -> {action}")
    
    try:
        success = False
        if action == "on":
            success = await kasa_agent.turn_on(ip)
        elif action == "off":
            success = await kasa_agent.turn_off(ip)
        elif action == "brightness":
            val = data.get('value')
            success = await kasa_agent.set_brightness(ip, val)
        elif action == "color":
            # value is {h, s, v} - convert to tuple for set_color
            h = data.get('value', {}).get('h', 0)
            s = data.get('value', {}).get('s', 100)
            v = data.get('value', {}).get('v', 100)
            success = await kasa_agent.set_color(ip, (h, s, v))
        
        if success:
            await sio.emit('kasa_update', {
                'ip': ip,
                'is_on': True if action == "on" else (False if action == "off" else None),
                'brightness': data.get('value') if action == "brightness" else None,
            })
 
        else:
             await sio.emit('error', {'msg': f"Failed to control device {ip}"})

    except Exception as e:
         print(f"Error controlling kasa: {e}")
         await sio.emit('error', {'msg': f"Kasa Control Error: {str(e)}"})

@sio.event
async def get_settings(sid):
    await sio.emit('settings', get_settings_payload())

@sio.event
async def update_settings(sid, data):
    # Generic update
    print(f"Updating settings: {data}")
    
    # Handle specific keys if needed
    if "tool_permissions" in data:
        SETTINGS["tool_permissions"].update(data["tool_permissions"])
        if audio_loop:
            audio_loop.update_permissions(SETTINGS["tool_permissions"])
        if text_chat_loop:
            text_chat_loop.update_permissions(SETTINGS["tool_permissions"])
            
    if "face_auth_enabled" in data:
        SETTINGS["face_auth_enabled"] = data["face_auth_enabled"]
        if not data["face_auth_enabled"]:
            # Turning OFF face auth -> auto-authenticate
            await sio.emit('auth_status', {'authenticated': True})
            if authenticator:
                authenticator.stop()
        else:
            # Turning ON face auth -> check if face is registered
            if authenticator and authenticator.is_registered():
                print("[SERVER] Face auth enabled. Lock will apply on next connection.")
            else:
                print("[SERVER] Face auth enabled but no face registered. Please register a face first.")

    if "camera_flipped" in data:
        SETTINGS["camera_flipped"] = data["camera_flipped"]
        print(f"[SERVER] Camera flip set to: {data['camera_flipped']}")

    save_settings()
    # Broadcast new full settings
    await sio.emit('settings', get_settings_payload())





# ============================================
# WAKE WORD DETECTION
# ============================================

@sio.event
async def start_wake_word(sid, data=None):
    """Start listening for 'Hey Smarty' wake word."""
    global wake_word_listener, wake_word_task
    
    print("[SERVER] Starting Wake Word Detection...")
    
    if wake_word_listener and wake_word_task and not wake_word_task.done():
        print("[SERVER] Wake word listener already running")
        await sio.emit('status', {'msg': 'Wake Word Already Active'})
        return
    
    # Callback when wake word is detected
    async def on_wake_word_detected():
        print("[SERVER] 🎤 Wake word detected! Activating Smarty...")
        await sio.emit('wake_word_detected', {'message': 'Hey Smarty detected!'})
        await sio.emit('status', {'msg': '🎤 Hey Smarty! How can I help?'})
        
        # Auto-start text chat if not already running
        if not text_chat_loop and not audio_loop:
            await start_text_chat(sid)
    
    try:
        # Get device index from data if provided
        device_index = data.get('device_index') if data else None
        threshold = data.get('threshold', 0.5) if data else 0.5
        
        wake_word_listener = get_wake_word_listener(
            on_wake_word=on_wake_word_detected,
            threshold=threshold,
            input_device_index=device_index
        )
        
        wake_word_task = asyncio.create_task(wake_word_listener.start())
        
        await sio.emit('status', {'msg': 'Wake Word Detection Active - Say "Hey Smarty"'})
        print("[SERVER] Wake word listener started successfully")
        
    except Exception as e:
        print(f"[SERVER] Error starting wake word: {e}")
        import traceback
        traceback.print_exc()
        await sio.emit('error', {'msg': f"Wake word error: {str(e)}"})


@sio.event
async def stop_wake_word(sid):
    """Stop wake word detection."""
    global wake_word_listener, wake_word_task
    
    if wake_word_listener:
        wake_word_listener.stop()
        wake_word_listener = None
        print("[SERVER] Wake word listener stopped")
    
    if wake_word_task and not wake_word_task.done():
        wake_word_task.cancel()
        wake_word_task = None
    
    await sio.emit('status', {'msg': 'Wake Word Detection Stopped'})


@sio.event
async def pause_wake_word(sid):
    """Pause wake word detection (e.g., while talking)."""
    if wake_word_listener:
        wake_word_listener.pause()
        await sio.emit('status', {'msg': 'Wake Word Paused'})


@sio.event
async def resume_wake_word(sid):
    """Resume wake word detection."""
    if wake_word_listener:
        wake_word_listener.resume()
        await sio.emit('status', {'msg': 'Wake Word Resumed'})


@sio.event
async def logout(sid):
    """Lock the system - require re-authentication."""
    global authenticator
    print("[SERVER] Logout requested. Locking system.")
    if authenticator:
        authenticator.authenticated = False
        authenticator.running = False
    await sio.emit('auth_status', {'authenticated': False})

@sio.event
async def check_registration(sid):
    """Check if a face is registered and handle auth flow."""
    global authenticator
    is_registered = authenticator.is_registered() if authenticator else False
    face_auth_on = SETTINGS.get("face_auth_enabled", False)
    
    await sio.emit('registration_status', {'registered': is_registered})
    
    if not face_auth_on:
        # Face auth is disabled, auto-authenticate
        await sio.emit('auth_status', {'authenticated': True})
    elif not is_registered:
        # No face registered, prompt for registration
        await sio.emit('auth_status', {'authenticated': False, 'needs_registration': True})
    else:
        # Face is registered, start auth loop
        await sio.emit('auth_status', {'authenticated': False})
        try:
            await authenticator.start_authentication_loop()
        except Exception as e:
            print(f"[SERVER] Auth loop error: {e}")
            await sio.emit('error', {'msg': f"Authentication error: {str(e)}"})

@sio.event
async def start_registration(sid):
    """Start the face registration camera loop."""
    global authenticator
    print("[SERVER] Starting face registration...")
    if not authenticator:
        try:
            authenticator = _create_authenticator()
        except Exception as e:
            await sio.emit('error', {'msg': f"Failed to create authenticator: {str(e)}"})
            return
    
    success = authenticator.start_registration_loop()
    if success:
        await sio.emit('auth_status', {'authenticated': False, 'is_registering': True})
    else:
        await sio.emit('error', {'msg': 'A face is already registered. Clear face data first.'})

@sio.event
async def capture_registration(sid):
    """Capture the current frame and register it as the reference face."""
    global authenticator
    print("[SERVER] Capturing face for registration...")
    if not authenticator:
        await sio.emit('error', {'msg': 'Authenticator not initialized.'})
        return
    
    success, message = authenticator.register_current_face()
    if success:
        # Enable face auth in settings
        SETTINGS["face_auth_enabled"] = True
        save_settings()
        await sio.emit('registration_success', {'message': message})
        await sio.emit('auth_status', {'authenticated': True})
        await sio.emit('settings', get_settings_payload())
        print(f"[SERVER] Face registered successfully. Face auth enabled.")
    else:
        await sio.emit('error', {'msg': message})

@sio.event
async def reset_registration(sid):
    """Reset (delete) face registration and re-register."""
    global authenticator
    print("[SERVER] Resetting face registration...")
    if authenticator:
        authenticator.delete_registration()
    # Recreate authenticator for fresh state
    try:
        authenticator = _create_authenticator()
    except Exception as e:
        print(f"[SERVER] Authenticator recreate failed: {e}")
    await sio.emit('registration_status', {'registered': False})
    await sio.emit('settings', get_settings_payload())

@sio.event
async def delete_registration(sid):
    """Delete the registered face data."""
    global authenticator
    print("[SERVER] Deleting face registration...")
    if authenticator:
        authenticator.delete_registration()
    # Disable face auth since there's no face to authenticate against
    SETTINGS["face_auth_enabled"] = False
    save_settings()
    # Recreate authenticator for fresh state
    try:
        authenticator = _create_authenticator()
    except Exception as e:
        print(f"[SERVER] Authenticator recreate failed: {e}")
    await sio.emit('auth_status', {'authenticated': True})
    await sio.emit('registration_status', {'registered': False})
    await sio.emit('settings', get_settings_payload())
    print("[SERVER] Face data cleared. Face auth disabled.")

if __name__ == "__main__":
    uvicorn.run(
        "server:app_socketio", 
        host="127.0.0.1", 
        port=8000, 
        reload=False, # Reload enabled causes spawn of worker which might miss the event loop policy patch
        loop="asyncio",
        reload_excludes=["temp_cad_gen.py", "output.stl", "*.stl"]
    )
