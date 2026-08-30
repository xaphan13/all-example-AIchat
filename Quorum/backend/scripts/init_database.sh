#!/bin/bash
# Initialize the database schema

set -e

# Navigate to backend directory
cd "$(dirname "$0")/.."

echo "Activating virtual environment..."
source venv/bin/activate

echo "Initializing database schema..."
python3 -m src.infrastructure.database.init_db init

echo ""
echo "Database initialized successfully!"
echo ""
echo "You can now run the application with:"
echo "  make run"
echo ""
echo "To create a migration after model changes:"
echo "  cd backend"
echo "  alembic revision --autogenerate -m 'description'"
echo "  alembic upgrade head"

