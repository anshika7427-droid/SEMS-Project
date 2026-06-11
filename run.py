import subprocess
import threading
import time
import webbrowser

# -----------------------------------
# START FASTAPI SERVER
# -----------------------------------

def start_fastapi():
    subprocess.run([
        "uvicorn",
        "app.main:app",
        "--reload",
        "--host",
        "127.0.0.1",
        "--port",
        "8000"
    ])

# -----------------------------------
# START STREAMLIT SERVER
# -----------------------------------

def start_streamlit():
    subprocess.run([
        "streamlit",
        "run",
        "dashboard/streamlit_app.py",
        "--server.port",
        "8501"
    ])

# -----------------------------------
# MAIN APPLICATION RUNNER
# -----------------------------------

if __name__ == "__main__":

    print("\n🚀 Starting AI-Based Education Recommendation System...\n")

    # Start FastAPI Thread
    fastapi_thread = threading.Thread(target=start_fastapi)

    # Start Streamlit Thread
    streamlit_thread = threading.Thread(target=start_streamlit)

    # Run both threads
    fastapi_thread.start()
    streamlit_thread.start()

    # Wait a few seconds before opening browser
    time.sleep(5)

    # Open Landing Page Automatically
    webbrowser.open("http://127.0.0.1:8000")

    print("✅ FastAPI running on http://127.0.0.1:8000")
    print("✅ Streamlit running on http://127.0.0.1:8501")