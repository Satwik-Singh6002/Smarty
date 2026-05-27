import asyncio
import socketio
import subprocess
import time
import sys

async def run_test():
    print("Starting backend server in unbuffered mode...")
    server_process = subprocess.Popen(
        [r"c:\Users\satwi\OneDrive\Desktop\Smarty\.venv\Scripts\python.exe", "-u", "backend/server.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=r"c:\Users\satwi\OneDrive\Desktop\Smarty\ada_v2"
    )
    
    # Wait for server to start
    await asyncio.sleep(4)
    
    sio = socketio.AsyncClient()
    received_status = []
    received_error = []
    
    @sio.on('auth_status')
    async def on_auth_status(data):
        print(f"[Client] Received auth_status: {data}")
        received_status.append(data)
        
    @sio.on('error')
    async def on_error(data):
        print(f"[Client] Received error: {data}")
        received_error.append(data)

    try:
        print("Connecting to Socket.IO server...")
        await sio.connect('http://127.0.0.1:8000')
        print("Connected.")
        
        # Check initial registration status
        print("Emitting check_registration...")
        await sio.emit('check_registration')
        await asyncio.sleep(1.5)
        
        print("Emitting start_registration...")
        await sio.emit('start_registration')
        await asyncio.sleep(3)
        
    except Exception as e:
        print(f"Exception during test: {e}")
    finally:
        await sio.disconnect()
        print("Disconnected.")
        server_process.terminate()
        server_process.wait()
        stdout, stderr = server_process.communicate()
        print("\n--- Server Stdout ---")
        print(stdout)
        print("\n--- Server Stderr ---")
        print(stderr)

if __name__ == "__main__":
    asyncio.run(run_test())
