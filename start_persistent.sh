#!/bin/bash
echo "Stopping old services..."
pkill -f "uvicorn"
pkill -f "next"
sleep 2

echo "Starting Backend..."
nohup python -m uvicorn web_api.main:app --host 0.0.0.0 --port 8000 --reload > backend.log 2>&1 &
PID_BACKEND=$!
echo "Backend started with PID $PID_BACKEND"

echo "Starting Frontend..."
cd web_ui
nohup npm run dev > frontend.log 2>&1 &
PID_FRONTEND=$!
echo "Frontend started with PID $PID_FRONTEND"

echo "Waiting for services to initialize..."
sleep 5

if lsof -i :8000 > /dev/null; then
    echo "✅ Backend is running on port 8000"
else
    echo "❌ Backend failed to start. Check backend.log"
fi

if lsof -i :3000 > /dev/null; then
    echo "✅ Frontend is running on port 3000"
else
    echo "❌ Frontend failed to start. Check frontend.log"
fi
