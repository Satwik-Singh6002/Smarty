"""
Voxel System Launcher for Smarty AI Assistant
Ported from old Smarty server.py and web_launcher.py
"""
import os
import sys
import socket
import threading
import http.server
import socketserver
import webbrowser
from typing import Dict, Any, Optional

# Global state
_server_thread = None
_server_port = None


def find_available_port(start_port: int = 8080, max_attempts: int = 10) -> int:
    """Find an available port starting from start_port."""
    for port in range(start_port, start_port + max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('localhost', port))
                return port
        except OSError:
            continue
    return start_port


def start_voxel_server(port: int = 8080, serve_dir: Optional[str] = None) -> Dict[str, Any]:
    """
    Start an HTTP server for the Voxel/3D system.
    
    Args:
        port: Port to start server on (will find available if taken)
        serve_dir: Directory to serve files from (defaults to ada_v2 root)
    """
    global _server_thread, _server_port
    
    # Check if already running
    if _server_thread and _server_thread.is_alive():
        return {
            "success": True,
            "port": _server_port,
            "message": f"Server already running at http://localhost:{_server_port}"
        }
    
    try:
        # Find available port
        available_port = find_available_port(port)
        _server_port = available_port
        
        # Determine serve directory
        if serve_dir:
            base_dir = serve_dir
        else:
            # Default to ada_v2 root directory
            current_dir = os.path.dirname(os.path.abspath(__file__))
            base_dir = os.path.dirname(current_dir)  # Go up from backend/
        
        def run_server():
            """Run HTTP server in background thread."""
            os.chdir(base_dir)
            
            class SilentHTTPHandler(http.server.SimpleHTTPRequestHandler):
                def log_message(self, format, *args):
                    pass  # Suppress logging
                
                def end_headers(self):
                    # Add CORS headers
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
                    self.send_header('Access-Control-Allow-Headers', 'Content-Type')
                    super().end_headers()
            
            handler = SilentHTTPHandler
            handler.extensions_map.update({
                '.html': 'text/html; charset=utf-8',
                '.js': 'application/javascript; charset=utf-8',
                '.css': 'text/css; charset=utf-8',
                '.json': 'application/json; charset=utf-8',
                '.png': 'image/png',
                '.jpg': 'image/jpeg',
                '.gif': 'image/gif',
                '.svg': 'image/svg+xml',
                '.mp3': 'audio/mpeg',
                '.mp4': 'video/mp4',
                '.webm': 'video/webm',
            })
            
            with socketserver.TCPServer(("", available_port), handler) as httpd:
                print(f"[VoxelLauncher] HTTP Server running at http://localhost:{available_port}")
                print(f"[VoxelLauncher] Serving from: {base_dir}")
                httpd.serve_forever()
        
        # Start server in daemon thread
        _server_thread = threading.Thread(target=run_server, daemon=True)
        _server_thread.start()
        
        return {
            "success": True,
            "port": available_port,
            "directory": base_dir,
            "message": f"HTTP server started at http://localhost:{available_port}"
        }
    
    except Exception as e:
        return {"success": False, "error": str(e)}


def launch_voxel_in_browser(html_file: str = "index.html") -> Dict[str, Any]:
    """
    Launch the Voxel/3D system in the default browser.
    Starts HTTP server if not already running.
    
    Args:
        html_file: HTML file to open (default: index.html)
    """
    global _server_port
    
    try:
        # Start server if not running
        if not _server_thread or not _server_thread.is_alive():
            result = start_voxel_server()
            if not result["success"]:
                return result
        
        # Build URL
        url = f"http://localhost:{_server_port}/{html_file}"
        
        # Open in browser
        webbrowser.open(url)
        
        return {
            "success": True,
            "url": url,
            "message": f"Voxel system opened at {url}"
        }
    
    except Exception as e:
        return {"success": False, "error": str(e)}


def stop_voxel_server() -> Dict[str, Any]:
    """Stop the HTTP server (note: daemon thread will stop when main program exits)."""
    global _server_thread, _server_port
    
    if _server_thread and _server_thread.is_alive():
        # Daemon threads auto-stop, but we clear state
        _server_thread = None
        _server_port = None
        return {"success": True, "message": "Server stopped"}
    
    return {"success": True, "message": "Server was not running"}


# Quick test
if __name__ == "__main__":
    print("Testing Voxel Launcher...")
    result = start_voxel_server()
    print(f"Server: {result}")
    
    if result["success"]:
        import time
        time.sleep(2)
        browser_result = launch_voxel_in_browser()
        print(f"Browser: {browser_result}")
        
        input("Press Enter to stop...")
