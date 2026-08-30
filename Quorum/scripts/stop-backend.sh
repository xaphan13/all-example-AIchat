#!/bin/bash

# Stop Backend Script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$PROJECT_ROOT/backend"
PID_FILE="$BACKEND_DIR/.backend.pid"

echo "🛑 Stopping Quorum Backend..."

if [ ! -f "$PID_FILE" ]; then
    echo "⚠️  No PID file found. Backend may not be running."
    
    # Try to find and kill uvicorn processes anyway
    PIDS=$(pgrep -f "uvicorn main:app")
    if [ -n "$PIDS" ]; then
        echo "Found running uvicorn processes: $PIDS"
        echo "Killing processes..."
        kill $PIDS 2>/dev/null
        sleep 1
        # Force kill if still running
        kill -9 $PIDS 2>/dev/null
        echo "✅ Processes terminated"
    else
        echo "No backend processes found"
    fi
    exit 0
fi

PID=$(cat "$PID_FILE")

if ps -p "$PID" > /dev/null 2>&1; then
    echo "Stopping backend process (PID: $PID)..."
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
    
    echo "✅ Backend stopped successfully"
else
    echo "⚠️  Process $PID not found (may have already stopped)"
fi

rm "$PID_FILE"

