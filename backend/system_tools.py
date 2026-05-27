"""
System Tools for Smarty AI Assistant
Full laptop control: files, processes, clipboard, WiFi, brightness,
power, keyboard, mouse, windows, battery, wallpaper, and more.
"""
import os
import sys
import subprocess
import datetime
import ctypes
import json
import shutil
import signal
import glob
import emoji
from typing import Dict, Any, Optional, List

# Optional imports with fallbacks
try:
    import pyautogui
    pyautogui.FAILSAFE = True
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

try:
    import pyperclip
    PYPERCLIP_AVAILABLE = True
except ImportError:
    PYPERCLIP_AVAILABLE = False


# ═══════════════════════════════════════════
#  TIME & DATE
# ═══════════════════════════════════════════

def get_current_time() -> Dict[str, Any]:
    now = datetime.datetime.now()
    return {"success": True, "time": now.strftime("%I:%M %p"), "message": f"The current time is {now.strftime('%I:%M %p')}"}

def get_current_date() -> Dict[str, Any]:
    now = datetime.datetime.now()
    return {"success": True, "date": now.strftime("%B %d, %Y"), "day": now.strftime("%A"),
            "message": f"Today is {now.strftime('%A, %B %d, %Y')}"}


# ═══════════════════════════════════════════
#  SCREENSHOT & SCREEN
# ═══════════════════════════════════════════

def take_screenshot(save_path: Optional[str] = None) -> Dict[str, Any]:
    if not PYAUTOGUI_AVAILABLE:
        return {"success": False, "error": "pyautogui not installed"}
    try:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = save_path or f"screenshot_{ts}.png"
        pyautogui.screenshot().save(filename)
        return {"success": True, "file_path": os.path.abspath(filename), "message": f"Screenshot saved as {filename}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def set_brightness(level: int) -> Dict[str, Any]:
    try:
        level = max(0, min(100, level))
        subprocess.run(
            ["powershell", "-Command",
             f"(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1,{level})"],
            capture_output=True, text=True, timeout=10
        )
        return {"success": True, "message": f"Brightness set to {level}%"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ═══════════════════════════════════════════
#  VOLUME CONTROL
# ═══════════════════════════════════════════

def control_volume(action: str) -> Dict[str, Any]:
    if not PYAUTOGUI_AVAILABLE:
        return {"success": False, "error": "pyautogui not installed"}
    try:
        action = action.lower().strip()
        if action == "up":
            for _ in range(5): pyautogui.press("volumeup")
            return {"success": True, "message": "Volume increased"}
        elif action == "down":
            for _ in range(5): pyautogui.press("volumedown")
            return {"success": True, "message": "Volume decreased"}
        elif action == "mute":
            pyautogui.press("volumemute")
            return {"success": True, "message": "Volume muted/unmuted"}
        elif action == "max":
            for _ in range(50): pyautogui.press("volumeup")
            return {"success": True, "message": "Volume set to maximum"}
        elif action == "min":
            for _ in range(50): pyautogui.press("volumedown")
            return {"success": True, "message": "Volume set to minimum"}
        else:
            return {"success": False, "error": f"Unknown action: {action}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ═══════════════════════════════════════════
#  SYSTEM INFO & BATTERY
# ═══════════════════════════════════════════

def get_system_info() -> Dict[str, Any]:
    if not PSUTIL_AVAILABLE:
        return {"success": False, "error": "psutil not installed"}
    try:
        cpu = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('C:\\' if sys.platform == 'win32' else '/')
        net = psutil.net_io_counters()
        return {
            "success": True, "cpu_percent": cpu,
            "memory_percent": mem.percent,
            "memory_available_gb": round(mem.available / (1024**3), 2),
            "memory_total_gb": round(mem.total / (1024**3), 2),
            "disk_percent": disk.percent,
            "disk_free_gb": round(disk.free / (1024**3), 2),
            "net_sent_mb": round(net.bytes_sent / (1024**2), 2),
            "net_recv_mb": round(net.bytes_recv / (1024**2), 2),
            "message": f"CPU: {cpu}%, RAM: {mem.percent}%, Disk: {disk.percent}%"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

def get_battery_status() -> Dict[str, Any]:
    if not PSUTIL_AVAILABLE:
        return {"success": False, "error": "psutil not installed"}
    try:
        bat = psutil.sensors_battery()
        if bat is None:
            return {"success": True, "message": "No battery detected (desktop PC)"}
        secs = bat.secsleft
        time_left = f"{secs // 3600}h {(secs % 3600) // 60}m" if secs > 0 else "Calculating..."
        return {
            "success": True, "percent": bat.percent, "plugged_in": bat.power_plugged,
            "time_left": time_left if not bat.power_plugged else "Charging",
            "message": f"Battery: {bat.percent}% {'(Plugged in)' if bat.power_plugged else f'({time_left} left)'}"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# ═══════════════════════════════════════════
#  POWER MANAGEMENT
# ═══════════════════════════════════════════

def lock_computer() -> Dict[str, Any]:
    try:
        if sys.platform == 'win32':
            ctypes.windll.user32.LockWorkStation()
            return {"success": True, "message": "System locked"}
        return {"success": False, "error": "Only supported on Windows"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def shutdown_computer(delay_seconds: int = 0) -> Dict[str, Any]:
    try:
        os.system(f"shutdown /s /t {delay_seconds}")
        msg = f"Shutting down in {delay_seconds} seconds" if delay_seconds else "Shutting down now"
        return {"success": True, "message": msg}
    except Exception as e:
        return {"success": False, "error": str(e)}

def restart_computer(delay_seconds: int = 0) -> Dict[str, Any]:
    try:
        os.system(f"shutdown /r /t {delay_seconds}")
        msg = f"Restarting in {delay_seconds} seconds" if delay_seconds else "Restarting now"
        return {"success": True, "message": msg}
    except Exception as e:
        return {"success": False, "error": str(e)}

def sleep_computer() -> Dict[str, Any]:
    try:
        if sys.platform == 'win32':
            import ctypes
            # Call SetSuspendState properly so it forces Sleep and not Hibernate
            # bHibernate=False, bForce=False, bWakeupEventsDisabled=False
            ctypes.windll.PowrProf.SetSuspendState(False, False, False)
        else:
            os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
        return {"success": True, "message": "System is going to sleep mode."}
    except Exception as e:
        return {"success": False, "error": str(e)}

def cancel_shutdown() -> Dict[str, Any]:
    try:
        os.system("shutdown /a")
        return {"success": True, "message": "Shutdown/restart cancelled"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ═══════════════════════════════════════════
#  APPLICATION MANAGEMENT
# ═══════════════════════════════════════════

def open_application(app_name: str) -> Dict[str, Any]:
    app_map = {
        "notepad": "notepad.exe", "calculator": "calc.exe", "calc": "calc.exe",
        "paint": "mspaint.exe", "wordpad": "wordpad.exe", "cmd": "cmd.exe",
        "command prompt": "cmd.exe", "terminal": "wt.exe", "powershell": "powershell.exe",
        "explorer": "explorer.exe", "file explorer": "explorer.exe",
        "task manager": "taskmgr.exe", "control panel": "control.exe",
        "settings": "ms-settings:", "snipping tool": "snippingtool.exe",
        "snip": "snippingtool.exe", "chrome": "chrome.exe", "google chrome": "chrome.exe",
        "firefox": "firefox.exe", "edge": "msedge.exe", "microsoft edge": "msedge.exe",
        "brave": "brave.exe", "vscode": "code", "visual studio code": "code",
        "spotify": "spotify.exe", "discord": "discord.exe", "slack": "slack.exe",
        "teams": "ms-teams.exe", "zoom": "zoom.exe", "obs": "obs64.exe",
        "vlc": "vlc.exe", "word": "winword.exe", "excel": "excel.exe",
        "powerpoint": "powerpnt.exe", "outlook": "outlook.exe",
        "steam": "steam.exe", "whatsapp": "WhatsApp.exe",
    }
    try:
        executable = app_map.get(app_name.lower().strip(), app_name)
        if sys.platform == 'win32':
            os.system(f"start {executable}")
        return {"success": True, "message": f"Opening {app_name}..."}
    except Exception as e:
        return {"success": False, "error": str(e)}

def close_application(app_name: str) -> Dict[str, Any]:
    try:
        process_map = {
            "chrome": "chrome.exe", "firefox": "firefox.exe", "edge": "msedge.exe",
            "notepad": "notepad.exe", "spotify": "spotify.exe", "discord": "Discord.exe",
            "vscode": "Code.exe", "visual studio code": "Code.exe",
            "word": "WINWORD.EXE", "excel": "EXCEL.EXE", "powerpoint": "POWERPNT.EXE",
            "vlc": "vlc.exe", "obs": "obs64.exe", "teams": "ms-teams.exe",
            "slack": "slack.exe", "zoom": "Zoom.exe", "steam": "steam.exe",
        }
        proc = process_map.get(app_name.lower().strip(), app_name)
        os.system(f"taskkill /IM {proc} /F")
        return {"success": True, "message": f"Closed {app_name}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ═══════════════════════════════════════════
#  PROCESS MANAGEMENT
# ═══════════════════════════════════════════

def list_running_processes(top_n: int = 15) -> Dict[str, Any]:
    if not PSUTIL_AVAILABLE:
        return {"success": False, "error": "psutil not installed"}
    try:
        procs = []
        for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                info = p.info
                procs.append(info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        procs.sort(key=lambda x: x.get('cpu_percent', 0) or 0, reverse=True)
        top = procs[:top_n]
        summary = "\n".join([f"  {p['name']} (PID {p['pid']}) — CPU: {p.get('cpu_percent',0)}%, RAM: {round(p.get('memory_percent',0),1)}%" for p in top])
        return {"success": True, "processes": top, "message": f"Top {top_n} processes:\n{summary}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def kill_process(name_or_pid: str) -> Dict[str, Any]:
    try:
        if name_or_pid.isdigit():
            os.system(f"taskkill /PID {name_or_pid} /F")
        else:
            os.system(f"taskkill /IM {name_or_pid} /F")
        return {"success": True, "message": f"Killed process: {name_or_pid}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ═══════════════════════════════════════════
#  FILE MANAGEMENT
# ═══════════════════════════════════════════

def create_file(path: str, content: str = "") -> Dict[str, Any]:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True) if os.path.dirname(path) else None
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return {"success": True, "message": f"Created file: {path}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def read_file(path: str) -> Dict[str, Any]:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read(10000)  # limit to 10K chars
        return {"success": True, "content": content, "message": f"Read {len(content)} chars from {path}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def delete_file(path: str) -> Dict[str, Any]:
    try:
        if os.path.isdir(path):
            shutil.rmtree(path)
            return {"success": True, "message": f"Deleted folder: {path}"}
        elif os.path.isfile(path):
            os.remove(path)
            return {"success": True, "message": f"Deleted file: {path}"}
        else:
            return {"success": False, "error": f"Path not found: {path}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def move_file(source: str, destination: str) -> Dict[str, Any]:
    try:
        shutil.move(source, destination)
        return {"success": True, "message": f"Moved {source} -> {destination}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def copy_file(source: str, destination: str) -> Dict[str, Any]:
    try:
        if os.path.isdir(source):
            shutil.copytree(source, destination)
        else:
            shutil.copy2(source, destination)
        return {"success": True, "message": f"Copied {source} -> {destination}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def rename_file(old_path: str, new_name: str) -> Dict[str, Any]:
    try:
        directory = os.path.dirname(old_path)
        new_path = os.path.join(directory, new_name)
        os.rename(old_path, new_path)
        return {"success": True, "message": f"Renamed to {new_name}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def list_directory(path: str = ".") -> Dict[str, Any]:
    try:
        items = os.listdir(path)
        details = []
        for item in items[:50]:  # limit to 50
            full = os.path.join(path, item)
            is_dir = os.path.isdir(full)
            size = os.path.getsize(full) if not is_dir else 0
            details.append({"name": item, "is_folder": is_dir, "size_kb": round(size/1024, 1)})
        return {"success": True, "items": details, "count": len(items),
                "message": f"{len(items)} items in {path}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def search_files(query: str, directory: str = "C:\\Users") -> Dict[str, Any]:
    try:
        results = []
        for root, dirs, files in os.walk(directory):
            # skip hidden/system dirs
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['node_modules', '__pycache__', '.git']]
            for f in files:
                if query.lower() in f.lower():
                    results.append(os.path.join(root, f))
                    if len(results) >= 20:
                        break
            if len(results) >= 20:
                break
        return {"success": True, "results": results, "message": f"Found {len(results)} files matching '{query}'"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def create_folder(path: str) -> Dict[str, Any]:
    try:
        os.makedirs(path, exist_ok=True)
        return {"success": True, "message": f"Created folder: {path}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ═══════════════════════════════════════════
#  CLIPBOARD
# ═══════════════════════════════════════════

def copy_to_clipboard(text: str) -> Dict[str, Any]:
    try:
        if PYPERCLIP_AVAILABLE:
            pyperclip.copy(text)
        else:
            subprocess.run(["clip"], input=text.encode('utf-8'), check=True)
        return {"success": True, "message": "Text copied to clipboard"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def get_clipboard() -> Dict[str, Any]:
    try:
        if PYPERCLIP_AVAILABLE:
            text = pyperclip.paste()
        else:
            result = subprocess.run(["powershell", "Get-Clipboard"], capture_output=True, text=True)
            text = result.stdout.strip()
        return {"success": True, "content": text, "message": f"Clipboard content: {text[:200]}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ═══════════════════════════════════════════
#  KEYBOARD & TYPING
# ═══════════════════════════════════════════

def type_text(text: str) -> Dict[str, Any]:
    if not PYAUTOGUI_AVAILABLE:
        return {"success": False, "error": "pyautogui not installed"}
    try:
        import time
        time.sleep(0.5)
        pyautogui.typewrite(text, interval=0.02) if text.isascii() else pyautogui.write(text)
        return {"success": True, "message": f"Typed: {text[:50]}..."}
    except Exception as e:
        return {"success": False, "error": str(e)}

def press_hotkey(keys: str) -> Dict[str, Any]:
    """Press a hotkey combo like 'ctrl+c', 'alt+tab', 'win+d'."""
    if not PYAUTOGUI_AVAILABLE:
        return {"success": False, "error": "pyautogui not installed"}
    try:
        key_list = [k.strip().lower() for k in keys.split('+')]
        key_map = {"ctrl": "ctrl", "alt": "alt", "shift": "shift", "win": "win",
                    "tab": "tab", "enter": "enter", "esc": "escape", "escape": "escape",
                    "space": "space", "delete": "delete", "backspace": "backspace",
                    "up": "up", "down": "down", "left": "left", "right": "right",
                    "home": "home", "end": "end", "pageup": "pageup", "pagedown": "pagedown",
                    "f1": "f1", "f2": "f2", "f3": "f3", "f4": "f4", "f5": "f5",
                    "f6": "f6", "f7": "f7", "f8": "f8", "f9": "f9", "f10": "f10",
                    "f11": "f11", "f12": "f12", "printscreen": "printscreen",
                    "prtsc": "printscreen", "insert": "insert"}
        mapped = [key_map.get(k, k) for k in key_list]
        pyautogui.hotkey(*mapped)
        return {"success": True, "message": f"Pressed: {keys}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def press_key(key: str) -> Dict[str, Any]:
    if not PYAUTOGUI_AVAILABLE:
        return {"success": False, "error": "pyautogui not installed"}
    try:
        pyautogui.press(key)
        return {"success": True, "message": f"Pressed key: {key}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ═══════════════════════════════════════════
#  WINDOW MANAGEMENT
# ═══════════════════════════════════════════

def minimize_all_windows() -> Dict[str, Any]:
    if not PYAUTOGUI_AVAILABLE:
        return {"success": False, "error": "pyautogui not installed"}
    try:
        pyautogui.hotkey('win', 'd')
        return {"success": True, "message": "All windows minimized (show desktop)"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def switch_window() -> Dict[str, Any]:
    if not PYAUTOGUI_AVAILABLE:
        return {"success": False, "error": "pyautogui not installed"}
    try:
        pyautogui.hotkey('alt', 'tab')
        return {"success": True, "message": "Switched to next window"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def maximize_window() -> Dict[str, Any]:
    if not PYAUTOGUI_AVAILABLE:
        return {"success": False, "error": "pyautogui not installed"}
    try:
        pyautogui.hotkey('win', 'up')
        return {"success": True, "message": "Window maximized"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def minimize_window() -> Dict[str, Any]:
    if not PYAUTOGUI_AVAILABLE:
        return {"success": False, "error": "pyautogui not installed"}
    try:
        pyautogui.hotkey('win', 'down')
        return {"success": True, "message": "Window minimized"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def close_window() -> Dict[str, Any]:
    if not PYAUTOGUI_AVAILABLE:
        return {"success": False, "error": "pyautogui not installed"}
    try:
        pyautogui.hotkey('alt', 'f4')
        return {"success": True, "message": "Window closed"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def snap_window(direction: str) -> Dict[str, Any]:
    if not PYAUTOGUI_AVAILABLE:
        return {"success": False, "error": "pyautogui not installed"}
    try:
        d = direction.lower().strip()
        key_map = {"left": "left", "right": "right", "up": "up", "down": "down"}
        if d in key_map:
            pyautogui.hotkey('win', key_map[d])
            return {"success": True, "message": f"Window snapped {d}"}
        return {"success": False, "error": f"Unknown direction: {d}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def open_task_view() -> Dict[str, Any]:
    if not PYAUTOGUI_AVAILABLE:
        return {"success": False, "error": "pyautogui not installed"}
    try:
        pyautogui.hotkey('win', 'tab')
        return {"success": True, "message": "Task view opened"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ═══════════════════════════════════════════
#  WIFI & NETWORK
# ═══════════════════════════════════════════

def get_wifi_networks() -> Dict[str, Any]:
    try:
        result = subprocess.run(["netsh", "wlan", "show", "networks"], capture_output=True, text=True, timeout=10)
        return {"success": True, "output": result.stdout, "message": "WiFi networks listed"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def connect_wifi(ssid: str) -> Dict[str, Any]:
    try:
        result = subprocess.run(["netsh", "wlan", "connect", f"name={ssid}"], capture_output=True, text=True, timeout=10)
        return {"success": True, "output": result.stdout, "message": f"Connecting to {ssid}..."}
    except Exception as e:
        return {"success": False, "error": str(e)}

def disconnect_wifi() -> Dict[str, Any]:
    try:
        subprocess.run(["netsh", "wlan", "disconnect"], capture_output=True, text=True, timeout=10)
        return {"success": True, "message": "WiFi disconnected"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def get_ip_address() -> Dict[str, Any]:
    try:
        result = subprocess.run(["ipconfig"], capture_output=True, text=True, timeout=10)
        return {"success": True, "output": result.stdout, "message": "IP configuration retrieved"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def ping_host(host: str) -> Dict[str, Any]:
    try:
        result = subprocess.run(["ping", "-n", "4", host], capture_output=True, text=True, timeout=15)
        return {"success": True, "output": result.stdout, "message": f"Ping results for {host}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def toggle_wifi(enable: bool = True) -> Dict[str, Any]:
    try:
        action = "enable" if enable else "disable"
        subprocess.run(["netsh", "interface", "set", "interface", "Wi-Fi", action],
                       capture_output=True, text=True, timeout=10)
        return {"success": True, "message": f"WiFi {'enabled' if enable else 'disabled'}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def toggle_bluetooth(enable: bool = True) -> Dict[str, Any]:
    try:
        # Uses PowerShell to toggle Bluetooth radio
        action = "true" if enable else "false"
        ps_cmd = f"""
        Add-Type -AssemblyName System.Runtime.WindowsRuntime
        [Windows.Devices.Radios.Radio,Windows.System.Devices,ContentType=WindowsRuntime] | Out-Null
        $radios = [Windows.Devices.Radios.Radio]::GetRadiosAsync().AsTask().Result
        $bt = $radios | Where-Object {{ $_.Kind -eq 'Bluetooth' }}
        if ($bt) {{ $bt.SetStateAsync({('On' if enable else 'Off')}).AsTask().Wait() }}
        """
        subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True, text=True, timeout=15)
        return {"success": True, "message": f"Bluetooth {'enabled' if enable else 'disabled'}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ═══════════════════════════════════════════
#  WALLPAPER & DISPLAY
# ═══════════════════════════════════════════

def set_wallpaper(image_path: str) -> Dict[str, Any]:
    try:
        abs_path = os.path.abspath(image_path)
        if not os.path.isfile(abs_path):
            return {"success": False, "error": f"Image not found: {abs_path}"}
        ctypes.windll.user32.SystemParametersInfoW(20, 0, abs_path, 3)
        return {"success": True, "message": f"Wallpaper set to {abs_path}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ═══════════════════════════════════════════
#  CLEANUP & MAINTENANCE
# ═══════════════════════════════════════════

def empty_recycle_bin() -> Dict[str, Any]:
    try:
        ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 7)
        return {"success": True, "message": "Recycle bin emptied"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def clear_temp_files() -> Dict[str, Any]:
    try:
        temp = os.environ.get('TEMP', os.path.join(os.environ['USERPROFILE'], 'AppData', 'Local', 'Temp'))
        count = 0
        for item in os.listdir(temp):
            try:
                full = os.path.join(temp, item)
                if os.path.isfile(full):
                    os.remove(full)
                    count += 1
                elif os.path.isdir(full):
                    shutil.rmtree(full, ignore_errors=True)
                    count += 1
            except:
                pass
        return {"success": True, "message": f"Cleared {count} temp items"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ═══════════════════════════════════════════
#  SHELL / CMD EXECUTION
# ═══════════════════════════════════════════

def run_shell_command(command: str) -> Dict[str, Any]:
    """Run any shell command and return output. USE WITH CAUTION."""
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout[:3000],
            "stderr": result.stderr[:1000],
            "message": result.stdout[:500] if result.returncode == 0 else f"Error: {result.stderr[:500]}"
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Command timed out after 30 seconds"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ═══════════════════════════════════════════
#  NOTIFICATIONS & ALERTS
# ═══════════════════════════════════════════

def show_notification(title: str, message: str) -> Dict[str, Any]:
    try:
        ps_cmd = f"""
        [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
        $xml = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
        $texts = $xml.GetElementsByTagName('text')
        $texts[0].AppendChild($xml.CreateTextNode('{title}')) | Out-Null
        $texts[1].AppendChild($xml.CreateTextNode('{message}')) | Out-Null
        $toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
        [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('Smarty AI').Show($toast)
        """
        subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True, timeout=10)
        return {"success": True, "message": f"Notification shown: {title}"}
    except Exception as e:
        # Fallback: use msg box
        try:
            ctypes.windll.user32.MessageBoxW(0, message, title, 0x40)
            return {"success": True, "message": f"Alert shown: {title}"}
        except:
            return {"success": False, "error": str(e)}

def set_timer(seconds: int, message: str = "Timer done!") -> Dict[str, Any]:
    """Set a timer that shows a notification after X seconds."""
    try:
        import threading
        def _timer_callback():
            show_notification("⏰ Smarty Timer", message)
        timer = threading.Timer(seconds, _timer_callback)
        timer.daemon = True
        timer.start()
        mins = seconds // 60
        secs = seconds % 60
        time_str = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"
        return {"success": True, "message": f"Timer set for {time_str}: '{message}'"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ═══════════════════════════════════════════
#  MEDIA CONTROL (Play/Pause/Next/Prev)
# ═══════════════════════════════════════════

def media_control(action: str) -> Dict[str, Any]:
    if not PYAUTOGUI_AVAILABLE:
        return {"success": False, "error": "pyautogui not installed"}
    try:
        action = action.lower().strip()
        media_keys = {
            "play": "playpause", "pause": "playpause", "playpause": "playpause",
            "next": "nexttrack", "skip": "nexttrack",
            "previous": "prevtrack", "prev": "prevtrack", "back": "prevtrack",
            "stop": "stop"
        }
        if action in media_keys:
            pyautogui.press(media_keys[action])
            return {"success": True, "message": f"Media: {action}"}
        return {"success": False, "error": f"Unknown media action: {action}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ═══════════════════════════════════════════
#  OPEN SPECIFIC FOLDERS
# ═══════════════════════════════════════════

def open_folder(path: str) -> Dict[str, Any]:
    try:
        abs_path = os.path.abspath(path)
        if sys.platform == 'win32':
            os.startfile(abs_path)
        return {"success": True, "message": f"Opened folder: {abs_path}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ═══════════════════════════════════════════
#  TEXT-TO-SPEECH (Smarty Voice — Edge TTS)
# ═══════════════════════════════════════════

# Smarty Voice Configuration
# en-GB-RyanNeural: Deep, refined British male — closest to Smarty/Paul Bettany
Smarty_VOICE = "en-GB-RyanNeural"
Smarty_RATE = "+8%"     # Slightly faster for that crisp AI delivery
Smarty_PITCH = "-6Hz"   # Slightly lower pitch for gravitas

# Hindi Voice Configuration
HINDI_VOICE = "hi-IN-MadhurNeural"  # Clear, professional adult male Hindi voice
HINDI_RATE = "+5%"
HINDI_PITCH = "+0Hz"

def speak_text(text: str, wait: bool = False) -> Dict[str, Any]:
    """Speaks text aloud using Smarty-like voice (Edge TTS with British neural voice)."""
    try:
        # Strip emojis
        text_no_emojis = emoji.replace_emoji(text, replace='')
        clean_text = text_no_emojis.strip()
        if not clean_text:
            return {"success": True, "message": "Nothing to speak (empty after cleanup)"}

        # Try Edge TTS first (high-quality neural voice)
        try:
            return _speak_edge_tts(clean_text, wait=wait)
        except Exception as e:
            print(f"[Smarty TTS] Edge TTS failed ({e}), falling back to Windows SAPI")
            return _speak_sapi_fallback(clean_text, wait=wait)

    except Exception as e:
        return {"success": False, "error": str(e)}


def _speak_edge_tts(text: str, wait: bool = False) -> Dict[str, Any]:
    """Use Edge TTS (Microsoft Neural voices) for Smarty-quality speech."""
    import asyncio
    import edge_tts
    import tempfile
    import threading
    import uuid
    import re

    # Auto-detect language and set custom voice configurations
    selected_voice = "en-GB-RyanNeural"  # Refined British male voice (J.A.R.V.I.S like)
    selected_rate = "+8%"
    selected_pitch = "-6Hz"

    force_hindi = False
    if "[HINGLISH]" in text:
        force_hindi = True
        text = text.replace("[HINGLISH]", "").strip()

    text_lower = text.lower()
    
    # 1. Native Script / Unicode Block Checks
    if force_hindi or bool(re.search(r'[\u0900-\u097F]', text)):
        # Hindi / Hinglish
        selected_voice = "hi-IN-MadhurNeural"
        selected_rate = "+5%"
        selected_pitch = "+0Hz"
    elif bool(re.search(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF]', text)):
        # Japanese (Hiragana/Katakana/Kanji)
        selected_voice = "ja-JP-KeitaNeural"
        selected_rate = "+5%"
        selected_pitch = "+0Hz"
    elif bool(re.search(r'[\u4E00-\u9FFF]', text)):
        # Chinese (Hanzi)
        selected_voice = "zh-CN-YunxiNeural"
        selected_rate = "+5%"
        selected_pitch = "+0Hz"
    elif bool(re.search(r'[\u0400-\u04FF]', text)):
        # Russian (Cyrillic)
        selected_voice = "ru-RU-DmitryNeural"
        selected_rate = "+5%"
        selected_pitch = "+0Hz"
    elif bool(re.search(r'[\u0600-\u06FF]', text)):
        # Arabic
        selected_voice = "ar-SA-HamedNeural"
        selected_rate = "+5%"
        selected_pitch = "+0Hz"
    else:
        # 2. European Language Heuristics (Regex for keywords and accent characters)
        is_spanish = bool(re.search(r'\b(hola|gracias|buenos|días|amigo|usted|sí|no|para|con|como|este|esta|todo|bien|hacer|tengo)\b|[¡¿áéíóúñÁÉÍÓÚÑ]', text_lower))
        is_french = bool(re.search(r'\b(bonjour|merci|oui|le|la|les|un|une|et|en|que|est|ce|pour|avec|mais|nous|vous|tout|faire)\b|[çœéèàùâêîôûëïüÇÉÈÀÙ]', text_lower))
        is_german = bool(re.search(r'\b(hallo|danke|ja|nein|der|die|das|ein|eine|und|in|dass|ist|es|für|mit|aber|wir|sie|ihr|gut|machen)\b|[äöüßÄÖÜ]', text_lower))
        is_italian = bool(re.search(r'\b(ciao|grazie|si|il|la|i|le|un|una|e|in|che|è|per|con|ma|noi|voi|tutto|fare)\b|[àèéìòóùÀÈÉÌÒÓÙ]', text_lower))
        is_portuguese = bool(re.search(r'\b(olá|obrigado|sim|o|a|os|as|um|uma|e|em|que|é|para|com|mas|nós|vocês|tudo|fazer)\b|[áéíóúâêôãõçÁÉÍÓÚÂÊÔÃÕÇ]', text_lower))

        if is_spanish:
            selected_voice = "es-ES-AlvaroNeural"
            selected_rate = "+6%"
            selected_pitch = "+0Hz"
        elif is_french:
            selected_voice = "fr-FR-HenriNeural"
            selected_rate = "+5%"
            selected_pitch = "+0Hz"
        elif is_german:
            selected_voice = "de-DE-KillianNeural"
            selected_rate = "+5%"
            selected_pitch = "+0Hz"
        elif is_italian:
            selected_voice = "it-IT-GianniNeural"
            selected_rate = "+5%"
            selected_pitch = "+0Hz"
        elif is_portuguese:
            selected_voice = "pt-BR-AntonioNeural"
            selected_rate = "+5%"
            selected_pitch = "+0Hz"

    async def _generate_and_play():
        # Generate speech with Smarty voice settings
        communicate = edge_tts.Communicate(
            text,
            voice=selected_voice,
            rate=selected_rate,
            pitch=selected_pitch
        )
        
        # Use unique temp file to avoid locking issues
        tmp_file = os.path.join(tempfile.gettempdir(), f"smarty_tts_{uuid.uuid4().hex[:8]}.mp3")
        await communicate.save(tmp_file)
        
        # Small delay to ensure file handle is released
        import time
        time.sleep(0.1)
        
        # Play the audio
        _play_audio_file(tmp_file, wait=True)
        
        # Cleanup temp file after playback
        try:
            os.remove(tmp_file)
        except Exception:
            pass

    def _run_in_thread():
        try:
            # Create a new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(_generate_and_play())
            loop.close()
        except Exception as e:
            print(f"[Smarty TTS] Playback error: {e}")

    # Run in background thread so it doesn't block by default
    thread = threading.Thread(target=_run_in_thread, daemon=not wait)
    thread.start()
    
    if wait:
        thread.join()
    
    return {"success": True, "message": f"Smarty speaking: {text[:50]}..."}


def _play_audio_file(file_path: str, wait: bool = False):
    """Play an audio file using pygame mixer."""
    try:
        import pygame
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        
        pygame.mixer.music.load(file_path)
        pygame.mixer.music.play()
        
        # Wait for playback to finish
        if wait:
            while pygame.mixer.music.get_busy():
                import time
                time.sleep(0.1)
            
    except ImportError:
        # Fallback: use system player
        if sys.platform == 'win32':
            # Use PowerShell to play the mp3
            ps_cmd = (
                f"Add-Type -AssemblyName presentationCore; "
                f"$player = New-Object System.Windows.Media.MediaPlayer; "
                f"$player.Open('{file_path}'); "
                f"$player.Play(); "
                f"Start-Sleep -Seconds 30" # Max 30s playback
            )
            if wait:
                # Wait for powershell to finish
                subprocess.run(["powershell", "-Command", ps_cmd], shell=True)
            else:
                subprocess.Popen(["powershell", "-Command", ps_cmd], shell=True)
    except Exception as e:
        print(f"[Smarty TTS] Audio playback error: {e}")


def _speak_sapi_fallback(text: str, wait: bool = False) -> Dict[str, Any]:
    """Fallback: Windows built-in SAPI voice."""
    import threading
    
    safe_text = text.replace("'", "''")
    ps_cmd = (
        "Add-Type -AssemblyName System.speech; "
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        "$v = $s.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Name -like '*David*' -or $_.VoiceInfo.Name -like '*Mark*' }; "
        "if ($v) { $s.SelectVoice($v[0].VoiceInfo.Name) }; "
        "$s.Rate = 1; "
        f"$s.Speak('{safe_text}')"
    )
    subprocess.Popen(["powershell", "-Command", ps_cmd])
    return {"success": True, "message": f"Speaking (SAPI fallback): {text[:50]}..."}


# ═══════════════════════════════════════════
#  CUSTOM MACROS & AUTOMATIONS
# ═══════════════════════════════════════════

def focus_mode() -> Dict[str, Any]:
    try:
        control_volume("mute")
        set_brightness(60)
        close_application("discord")
        close_application("spotify")
        open_application("vscode")
        import webbrowser
        webbrowser.open("https://github.com")
        webbrowser.open("https://stackoverflow.com")
        return {"success": True, "message": "Focus Mode activated! Distractions closed, brightness/volume optimized, and dev tools opened."}
    except Exception as e:
        return {"success": False, "error": str(e)}

def chill_mode() -> Dict[str, Any]:
    try:
        minimize_all_windows()
        set_brightness(40)
        for _ in range(5): 
            control_volume("up")
        open_application("spotify")
        import webbrowser
        webbrowser.open("https://netflix.com")
        webbrowser.open("https://youtube.com")
        return {"success": True, "message": "Chill Mode activated! Windows minimized, Spotify, Netflix, and YouTube opened."}
    except Exception as e:
        return {"success": False, "error": str(e)}

def morning_cleanup() -> Dict[str, Any]:
    try:
        empty_res = empty_recycle_bin()
        temp_res = clear_temp_files()
        return {"success": True, "message": f"Morning Cleanup complete! {empty_res.get('message', '')}. {temp_res.get('message', '')}."}
    except Exception as e:
        return {"success": False, "error": str(e)}

def dev_setup() -> Dict[str, Any]:
    try:
        open_application("vscode")
        open_application("terminal")
        import webbrowser
        webbrowser.open("http://localhost:3000")
        return {"success": True, "message": "Development setup complete! VS Code, Terminal, and Localhost started."}
    except Exception as e:
        return {"success": False, "error": str(e)}

def gaming_mode() -> Dict[str, Any]:
    try:
        set_brightness(100)
        for _ in range(5): 
            control_volume("up")
        close_application("vscode")
        close_application("chrome")
        close_application("msedge")
        open_application("discord")
        return {"success": True, "message": "Gaming Mode activated! Brightness at max, volume up, browsers and Dev Tools closed, Discord open."}
    except Exception as e:
        return {"success": False, "error": str(e)}

def night_mode() -> Dict[str, Any]:
    try:
        minimize_all_windows()
        set_brightness(20)
        for _ in range(3):
            control_volume("down")
        open_application("spotify")
        return {"success": True, "message": "Night Mode activated! Brightness and volume reduced, all windows minimized, Spotify open for chill music."}
    except Exception as e:
        return {"success": False, "error": str(e)}

def open_personal_link(target: str) -> Dict[str, Any]:
    try:
        import webbrowser
        links = {
            "portfolio1": "https://satwik-portfolio-orpin.vercel.app/",
            "portfolio2": "https://satwik-techsavvy.vercel.app/",
            "github": "https://github.com/Satwik-Singh6002"
        }
        if target in links:
            webbrowser.open(links[target])
            return {"success": True, "message": f"Opened {target} successfully!"}
        return {"success": False, "error": f"Unknown link target: {target}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def boss_protocol() -> Dict[str, Any]:
    """Stealth Mode / Panic Button: instantly minimize all windows, mute audio, and open productive work apps."""
    try:
        control_volume("mute")
        minimize_all_windows()
        import webbrowser
        open_application("notepad")
        webbrowser.open("https://github.com")
        webbrowser.open("https://docs.google.com/spreadsheets")
        show_notification("Guardian Mode", "Stealth workspace restored successfully.")
        return {"success": True, "message": "Boss Protocol activated. Audio muted, windows minimized, and productive workspace restored."}
    except Exception as e:
        return {"success": False, "error": str(e)}


def self_evolution_sandbox(code_string: str) -> Dict[str, Any]:
    """Runs Python code dynamically in a temporary file and returns stdout/stderr. Used for self-debugging and scripting."""
    try:
        temp_file = os.path.join(os.path.dirname(__file__), "temp_evolve.py")
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write(code_string)
        
        import sys
        result = subprocess.run([sys.executable, temp_file], capture_output=True, text=True, timeout=15)
        
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except:
                pass
            
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
            "message": f"Execution finished with exit code {result.returncode}."
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Execution timed out after 15 seconds."}
    except Exception as e:
        return {"success": False, "error": str(e)}


# Quick test
if __name__ == "__main__":
    print("Testing system tools...")
    print(f"Time: {get_current_time()}")
    print(f"Date: {get_current_date()}")
    print(f"System Info: {get_system_info()}")
    print(f"Battery: {get_battery_status()}")
