#!/bin/bash
# Set explicit DB path
export YKS_DB_PATH="$(pwd)/YKS_LGS_HomeworkManager_v2.db"
echo "Using DB: $YKS_DB_PATH"

# Kill old
lsof -ti:8000 | xargs kill -9
lsof -ti:3000 | xargs kill -9
sleep 1

# Start Backend (No Reload for Stability)
cd "$(dirname "$0")"
if [ -f ".venv/bin/python" ]; then
    PYTHON_EXEC=".venv/bin/python"
else
    PYTHON_EXEC=".venv_old_20251029132201/bin/python"
fi
nohup "$PYTHON_EXEC" -m uvicorn web_api.main:app --host 0.0.0.0 --port 8000 > backend.log 2>&1 &
echo "Backend started."

# Start Frontend
cd web_ui
nohup npm run dev > frontend.log 2>&1 &
echo "Frontend started."
