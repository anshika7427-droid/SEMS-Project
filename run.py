import subprocess
import time
import webbrowser
import sys
from pathlib import Path

def start_server():
    print("\n🚀 Starting AI-Based Education Recommendation System (SEMS Backend)...\n")
    
    try:
        # Start uvicorn as a subprocess using the current Python executable
        proc = subprocess.Popen([
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--reload",
            "--host",
            "127.0.0.1",
            "--port",
            "8000"
        ])
        
        # Wait a couple of seconds for the server to bind
        time.sleep(2)
        
        # Open Landing Page Automatically
        print("✅ Opening browser at http://127.0.0.1:8000")
        webbrowser.open("http://127.0.0.1:8000")
        
        # Wait for the process to exit
        proc.wait()
    except KeyboardInterrupt:
        print("\n👋 Server stopped.")
        sys.exit(0)

if __name__ == "__main__":
    start_server()