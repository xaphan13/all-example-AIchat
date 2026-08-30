# Backend Makefile for Quorum

.PHONY: help install start stop restart clean test lint

help:
	@echo "Quorum Backend - Available Commands:"
	@echo "  make install    - Create virtual environment and install dependencies"
	@echo "  make start      - Start the backend server"
	@echo "  make stop       - Stop the backend server"
	@echo "  make restart    - Restart the backend server"
	@echo "  make clean      - Clean up cache and temporary files"
	@echo "  make test       - Run tests (if available)"
	@echo "  make lint       - Run linter (if available)"

install:
	@echo "📦 Installing backend dependencies..."
	python3 -m venv venv
	. venv/bin/activate && pip install --upgrade pip
	. venv/bin/activate && pip install -r requirements.txt
	@echo "✅ Backend dependencies installed"

start:
	@echo "🚀 Starting backend..."
	@bash ../scripts/start-backend.sh

stop:
	@echo "🛑 Stopping backend..."
	@bash ../scripts/stop-backend.sh

restart: stop start
	@echo "🔄 Backend restarted"

clean:
	@echo "🧹 Cleaning up..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	find . -type f -name ".DS_Store" -delete 2>/dev/null || true
	rm -f .backend.pid
	@echo "✅ Cleanup complete"

test:
	@echo "🧪 Running tests..."
	@. venv/bin/activate && PYTHONPATH=. python3 -m pytest tests/ -v --cov=src --cov-report=html --cov-report=term

lint:
	@echo "🔍 Running linter..."
	@. venv/bin/activate && python3 -m pylint *.py || echo "Linter not configured yet"

dev:
	@echo "🔧 Starting backend in development mode..."
	@. venv/bin/activate && python3 -m uvicorn src.app:app --reload --host 0.0.0.0 --port 8000

status:
	@if [ -f .backend.pid ]; then \
		PID=$$(cat .backend.pid); \
		if ps -p $$PID > /dev/null 2>&1; then \
			echo "✅ Backend is running (PID: $$PID)"; \
		else \
			echo "❌ Backend is not running (stale PID file)"; \
		fi \
	else \
		echo "❌ Backend is not running"; \
	fi

