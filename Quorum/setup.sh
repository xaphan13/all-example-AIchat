#!/bin/bash

echo "🚀 Setting up Multi-Agent Collaboration System"
echo "=============================================="

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Backend Setup
echo -e "\n${BLUE}📦 Setting up Backend...${NC}"
cd backend

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Setup .env file
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠️  Creating .env file from template...${NC}"
    cp config/env_template.txt .env
    echo -e "${YELLOW}⚠️  Please edit backend/.env with your API keys!${NC}"
else
    echo -e "${GREEN}✓ .env file already exists${NC}"
fi

cd ..

# Database Setup
echo -e "\n${BLUE}🗄️  Setting up Database...${NC}"
bash backend/scripts/setup_postgres.sh

# Frontend Setup
echo -e "\n${BLUE}📦 Setting up Frontend...${NC}"
cd frontend

# Install npm dependencies
echo "Installing Node dependencies..."
npm install

cd ..

# Summary
echo -e "\n${GREEN}✅ Setup Complete!${NC}"
echo -e "\n${BLUE}Next Steps:${NC}"
echo "1. Edit backend/.env with your API keys"
echo "2. Start the application using the Makefile:"
echo "   make start          # Start both backend and frontend"
echo "   make start-backend  # Start only backend"
echo "   make start-frontend # Start only frontend"
echo ""
echo "   Or manually:"
echo "   cd backend && source venv/bin/activate && uvicorn src.app:app --reload"
echo "   cd frontend && npm run dev"
echo ""
echo "🌐 Frontend: http://localhost:5173"
echo "🔧 Backend:  http://localhost:8000"
echo "🗄️  Database: postgresql://quorum:quorum@localhost:5432/quorum"
echo ""

