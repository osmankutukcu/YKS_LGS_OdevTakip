import subprocess
import time
import os
import signal
import sys

def run_servers():
    print("🚀 Starting YKS/LGS Web Application...")
    base_dir = os.path.dirname(os.path.abspath(__file__))
    os.environ["YKS_DB_PATH"] = os.path.join(base_dir, "YKS_LGS_HomeworkManager.db")
    
    # 1. Start Backend (FastAPI)
    print("backend starting (Port 8000)...")
    backend = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "web_api.main:app", "--host", "0.0.0.0", "--port", "8000"],
        cwd=os.getcwd()
    )
    
    # 2. Start Frontend (Next.js)
    print("frontend starting (Port 3000)...")
    # Using 'npm run dev' inside web_ui folder
    frontend = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=os.path.join(os.getcwd(), "web_ui")
    )
    
    print("\n✅ Systems are GO!")
    print("🌍 Frontend: http://localhost:3000")
    print("🔌 Backend:  http://localhost:8000")
    print("\nPress Ctrl+C to stop both servers.")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping servers...")
        backend.terminate()
        frontend.terminate()
        print("Done.")

if __name__ == "__main__":
    run_servers()
