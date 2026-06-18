import subprocess
import time
import webbrowser
import sys
import os
from pathlib import Path

def start_server():
    print("\n🚀 Starting AI-Based Education Recommendation System (SEMS Backend)...\n")
    
    host = os.getenv("HOST", "127.0.0.1")
    port = os.getenv("PORT", "8000")
    
    try:
        # Start uvicorn as a subprocess using the current Python executable
        proc = subprocess.Popen([
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--reload",
            "--host",
            host,
            "--port",
            port
        ])
        
        # Wait a couple of seconds for the server to bind
        time.sleep(2)
        
        # Open Landing Page Automatically
        web_host = host if host != "0.0.0.0" else "127.0.0.1"
        print(f"✅ Opening browser at http://{web_host}:{port}")
        webbrowser.open(f"http://{web_host}:{port}")
        
        # Wait for the process to exit
        proc.wait()
    except KeyboardInterrupt:
        print("\n👋 Server stopped.")
        sys.exit(0)

if __name__ == "__main__":
    start_server()