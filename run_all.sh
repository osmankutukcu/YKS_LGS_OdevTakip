#!/bin/bash
echo "Stopping old processes..."
lsof -ti:8000 | xargs kill -9 2>/dev/null
lsof -ti:3000 | xargs kill -9 2>/dev/null
sleep 2

cd "$(dirname "$0")"
export YKS_DB_PATH="$(pwd)/YKS_LGS_HomeworkManager.db"
if [ -f ".venv/bin/python" ]; then
    PYTHON_EXEC=".venv/bin/python"
else
    PYTHON_EXEC=".venv_old_20251029132201/bin/python"
fi
"$PYTHON_EXEC" -m uvicorn web_api.main:app --host 0.0.0.0 --port 8000 > backend.log 2>&1 &
BACKEND_PID=$!
echo "Backend PID: $BACKEND_PID"

echo "Starting Frontend..."
cd web_ui
npm run dev > frontend.log 2>&1 &
FRONTEND_PID=$!
echo "Frontend PID: $FRONTEND_PID"

echo "Waiting for services to initialize..."
sleep 5
echo "Done."
