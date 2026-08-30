# Frontend Makefile for Quorum

.PHONY: help install start stop restart clean build dev lint

help:
	@echo "Quorum Frontend - Available Commands:"
	@echo "  make install    - Install dependencies"
	@echo "  make start      - Start the frontend dev server"
	@echo "  make stop       - Stop the frontend dev server"
	@echo "  make restart    - Restart the frontend dev server"
	@echo "  make build      - Build for production"
	@echo "  make dev        - Start development server (npm run dev)"
	@echo "  make clean      - Clean up node_modules and build artifacts"
	@echo "  make lint       - Run linter"

install:
	@echo "📦 Installing frontend dependencies..."
	npm install
	@echo "✅ Frontend dependencies installed"

start:
	@echo "🚀 Starting frontend..."
	@bash ../scripts/start-frontend.sh

stop:
	@echo "🛑 Stopping frontend..."
	@bash ../scripts/stop-frontend.sh

restart: stop start
	@echo "🔄 Frontend restarted"

dev:
	@echo "🔧 Starting frontend in development mode..."
	npm run dev

build:
	@echo "🏗️  Building frontend for production..."
	npm run build
	@echo "✅ Build complete"

preview:
	@echo "👀 Previewing production build..."
	npm run preview

clean:
	@echo "🧹 Cleaning up..."
	rm -rf node_modules
	rm -rf dist
	rm -f .frontend.pid
	@echo "✅ Cleanup complete"

lint:
	@echo "🔍 Running linter..."
	npm run lint || echo "Linter configuration needed"

status:
	@if [ -f .frontend.pid ]; then \
		PID=$$(cat .frontend.pid); \
		if ps -p $$PID > /dev/null 2>&1; then \
			echo "✅ Frontend is running (PID: $$PID)"; \
		else \
			echo "❌ Frontend is not running (stale PID file)"; \
		fi \
	else \
		echo "❌ Frontend is not running"; \
	fi

