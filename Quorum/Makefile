# Root Makefile for Quorum

.PHONY: help install start stop restart status clean build dev test

help:
	@echo "Quorum - Available Commands:"
	@echo ""
	@echo "Setup & Installation:"
	@echo "  make install         - Install all dependencies (backend + frontend)"
	@echo "  make install-backend - Install backend dependencies only"
	@echo "  make install-frontend- Install frontend dependencies only"
	@echo ""
	@echo "Start & Stop:"
	@echo "  make start           - Start both backend and frontend in background"
	@echo "  make stop            - Stop both backend and frontend"
	@echo "  make restart         - Restart both services"
	@echo "  make start-backend   - Start backend only"
	@echo "  make start-frontend  - Start frontend only"
	@echo "  make stop-backend    - Stop backend only"
	@echo "  make stop-frontend   - Stop frontend only"
	@echo ""
	@echo "Development:"
	@echo "  make run             - Run both services in foreground (with visible output)"
	@echo "  make dev             - Alias for 'make run'"
	@echo "  make status          - Check status of both services"
	@echo "  make build           - Build frontend for production"
	@echo ""
	@echo "Maintenance:"
	@echo "  make clean           - Clean all build artifacts and caches"
	@echo "  make clean-backend   - Clean backend artifacts only"
	@echo "  make clean-frontend  - Clean frontend artifacts only"

# Installation targets
install: install-backend install-frontend
	@echo "✅ All dependencies installed"

install-backend:
	@echo "📦 Installing backend dependencies..."
	@cd backend && $(MAKE) install

install-frontend:
	@echo "📦 Installing frontend dependencies..."
	@cd frontend && $(MAKE) install

# Start/Stop targets
start: start-backend start-frontend
	@echo "✅ Both services started"
	@echo "Backend:  http://localhost:8000"
	@echo "Frontend: http://localhost:5173"

stop: stop-backend stop-frontend
	@echo "✅ Both services stopped"

start-backend:
	@bash scripts/start-backend.sh

start-frontend:
	@bash scripts/start-frontend.sh

stop-backend:
	@bash scripts/stop-backend.sh

stop-frontend:
	@bash scripts/stop-frontend.sh

restart: stop start
	@echo "✅ Both services restarted"

restart-backend:
	@cd backend && $(MAKE) restart

restart-frontend:
	@cd frontend && $(MAKE) restart

# Development targets
dev: run

run:
	@echo "🔧 Starting both services in foreground mode..."
	@echo "Backend:  http://localhost:8000"
	@echo "Frontend: http://localhost:5173"
	@echo ""
	@echo "Press Ctrl+C to stop both services"
	@echo ""
	@bash scripts/start-backend.sh foreground & bash scripts/start-frontend.sh foreground & wait

status:
	@echo "📊 Service Status:"
	@echo ""
	@echo "Backend:"
	@cd backend && $(MAKE) status
	@echo ""
	@echo "Frontend:"
	@cd frontend && $(MAKE) status

# Build targets
build:
	@cd frontend && $(MAKE) build

# Clean targets
clean: clean-backend clean-frontend
	@echo "✅ All artifacts cleaned"

clean-backend:
	@cd backend && $(MAKE) clean

clean-frontend:
	@cd frontend && $(MAKE) clean

# Test targets
test:
	@echo "🧪 Running all tests..."
	@cd backend && $(MAKE) test

lint:
	@echo "🔍 Running linters..."
	@cd backend && $(MAKE) lint
	@cd frontend && $(MAKE) lint

# Quick setup (install + start)
setup: install start
	@echo "✅ Setup complete! Services are running."
	@echo "Backend:  http://localhost:8000"
	@echo "Frontend: http://localhost:5173"

