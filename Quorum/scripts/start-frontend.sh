#!/bin/bash

# Start Frontend Script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
PID_FILE="$FRONTEND_DIR/.frontend.pid"
FOREGROUND_MODE="${1:-background}"

echo "🚀 Starting Quorum Frontend..."

# Check if port 5173 is in use and clear it
PORT_PID=$(lsof -ti:5173)
if [ -n "$PORT_PID" ]; then
    echo "🧹 Port 5173 is in use (PID: $PORT_PID). Clearing..."
    kill -9 $PORT_PID 2>/dev/null
    sleep 1
fi

# Clean up any stale PID file
if [ -f "$PID_FILE" ]; then
    echo "🧹 Cleaning up stale PID file..."
    rm "$PID_FILE"
fi

# Check if node_modules exists
if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
    echo "⚠️  node_modules not found. Installing dependencies..."
    cd "$FRONTEND_DIR"
    npm install
    if [ $? -ne 0 ]; then
        echo "❌ Failed to install dependencies"
        exit 1
    fi
fi

if [ "$FOREGROUND_MODE" = "foreground" ]; then
    # Start Vite dev server in foreground mode (output visible)
    cd "$FRONTEND_DIR"
    echo "✅ Frontend starting in foreground mode..."
    echo "🌐 Server running on http://localhost:5173"
    npm run dev
else
    # Start Vite dev server in the background
    cd "$FRONTEND_DIR"
    npm run dev > /dev/null 2>&1 &
    FRONTEND_PID=$!
    
    # Save PID
    echo $FRONTEND_PID > "$PID_FILE"
    
    # Wait a moment and check if it started successfully
    sleep 2
    if ps -p "$FRONTEND_PID" > /dev/null 2>&1; then
        echo "✅ Frontend started successfully (PID: $FRONTEND_PID)"
        echo "🌐 Server running on http://localhost:5173"
    else
        echo "❌ Failed to start frontend"
        rm "$PID_FILE"
        exit 1
    fi
fi

