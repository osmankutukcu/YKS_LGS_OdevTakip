
import subprocess
import sys
import time
import os
import signal

def launch():
    print("Killing old processes...")
    try:
        subprocess.run("lsof -ti:8000 | xargs kill -9", shell=True)
        subprocess.run("lsof -ti:3000 | xargs kill -9", shell=True)
    except:
        pass
    
    cwd = os.path.dirname(os.path.abspath(__file__))
    web_ui_cwd = os.path.join(cwd, "web_ui")
    
    # Define env with DB path override
    env = os.environ.copy()
    db_path = os.path.join(cwd, "YKS_LGS_HomeworkManager.db")
    if os.path.exists(db_path):
        print(f"Using Database: {db_path}")
        env["YKS_DB_PATH"] = db_path
    else:
        print("Warning: v2 Database not found in CWD!")

    print("Starting Backend...")
    # Use setsid to start in a new session (detached)
    backend = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "web_api.main:app", "--host", "0.0.0.0", "--port", "8000"],
        cwd=cwd,
        env=env, # Pass the custom env
        stdout=open("backend.log", "w"),
        stderr=subprocess.STDOUT,
        start_new_session=True
    )
    print(f"Backend PID: {backend.pid}")
    
    print("Starting Frontend...")
    frontend = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=web_ui_cwd,
        stdout=open("frontend.log", "w"),
        stderr=subprocess.STDOUT,
        start_new_session=True
    )
    print(f"Frontend PID: {frontend.pid}")
    
    print("Services started. Exiting launcher.")

if __name__ == "__main__":
    launch()
