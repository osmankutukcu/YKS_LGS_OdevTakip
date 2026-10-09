#!/bin/bash
# Kill existing processes
echo "Cleaning up ports..."
lsof -ti:8000 | xargs kill -9 2>/dev/null
lsof -ti:3000 | xargs kill -9 2>/dev/null
pkill -f "uvicorn"
pkill -f "next"

# Wait a moment
sleep 2

# Start Backend
echo "Starting Backend..."
cd "$(dirname "$0")"
if [ -f ".venv/bin/python" ]; then
    PYTHON_EXEC=".venv/bin/python"
else
    PYTHON_EXEC=".venv_old_20251029132201/bin/python"
fi
nohup "$PYTHON_EXEC" -m uvicorn web_api.main:app --host 0.0.0.0 --port 8000 --reload > backend.log 2>&1 &
BACKEND_PID=$!
echo "Backend started (PID: $BACKEND_PID)"

# Start Frontend
echo "Starting Frontend..."
cd web_ui
nohup npm run dev > frontend.log 2>&1 &
FRONTEND_PID=$!
echo "Frontend started (PID: $FRONTEND_PID)"

# Summary
echo "Services launched. Logs are in backend.log and web_ui/frontend.log"
