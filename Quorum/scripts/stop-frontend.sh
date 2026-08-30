#!/bin/bash

# Stop Frontend Script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
PID_FILE="$FRONTEND_DIR/.frontend.pid"

echo "🛑 Stopping Quorum Frontend..."

if [ ! -f "$PID_FILE" ]; then
    echo "⚠️  No PID file found. Frontend may not be running."
    
    # Try to find and kill vite processes anyway
    PIDS=$(pgrep -f "vite")
    if [ -n "$PIDS" ]; then
        echo "Found running vite processes: $PIDS"
        echo "Killing processes..."
        kill $PIDS 2>/dev/null
        sleep 1
        # Force kill if still running
        kill -9 $PIDS 2>/dev/null
        echo "✅ Processes terminated"
    else
        echo "No frontend processes found"
    fi
    exit 0
fi

PID=$(cat "$PID_FILE")

if ps -p "$PID" > /dev/null 2>&1; then
    echo "Stopping frontend process (PID: $PID)..."
    kill "$PID" 2>/dev/null
    
    # Wait for graceful shutdown
    for i in {1..5}; do
        if ! ps -p "$PID" > /dev/null 2>&1; then
            break
        fi
        sleep 1
    done
    
    # Force kill if still running
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "Force killing process..."
        kill -9 "$PID" 2>/dev/null
    fi
    
    echo "✅ Frontend stopped successfully"
else
    echo "⚠️  Process $PID not found (may have already stopped)"
fi

rm "$PID_FILE"

