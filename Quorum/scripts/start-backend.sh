#!/bin/bash

# Start Backend Script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$PROJECT_ROOT/backend"
VENV_DIR="$BACKEND_DIR/venv"
PID_FILE="$BACKEND_DIR/.backend.pid"
FOREGROUND_MODE="${1:-foreground}"

echo "🚀 Starting Quorum Backend..."

# Check if port 8000 is in use and clear it
PORT_PID=$(lsof -ti:8000)
if [ -n "$PORT_PID" ]; then
    echo "🧹 Port 8000 is in use (PID: $PORT_PID). Clearing..."
    kill -9 $PORT_PID 2>/dev/null
    sleep 1
fi

# Clean up any stale PID file
if [ -f "$PID_FILE" ]; then
    echo "🧹 Cleaning up stale PID file..."
    rm "$PID_FILE"
fi

# Check if virtual environment exists
if [ ! -d "$VENV_DIR" ]; then
    echo "❌ Virtual environment not found at $VENV_DIR"
    echo "Please run: cd backend && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Check if .env file exists
if [ ! -f "$BACKEND_DIR/.env" ]; then
    echo "⚠️  Warning: .env file not found in backend directory"
    echo "Please create one based on env_template.txt"
fi

# Activate virtual environment and start server
cd "$BACKEND_DIR"
source "$VENV_DIR/bin/activate"

if [ "$FOREGROUND_MODE" = "foreground" ]; then
    # Start uvicorn in foreground mode (output visible)
    echo "✅ Backend starting in foreground mode..."
    echo "📡 Server running on http://localhost:8000"
    python3 -m uvicorn src.app:app --host 0.0.0.0 --port 8000 --reload
else
    # Start uvicorn in the background
    python3 -m uvicorn src.app:app --host 0.0.0.0 --port 8000 --reload > /dev/null 2>&1 &
    BACKEND_PID=$!
    
    # Save PID
    echo $BACKEND_PID > "$PID_FILE"
    
    # Wait a moment and check if it started successfully
    sleep 2
    if ps -p "$BACKEND_PID" > /dev/null 2>&1; then
        echo "✅ Backend started successfully (PID: $BACKEND_PID)"
        echo "📡 Server running on http://localhost:8000"
    else
        echo "❌ Failed to start backend"
        rm "$PID_FILE"
        exit 1
    fi
fi

