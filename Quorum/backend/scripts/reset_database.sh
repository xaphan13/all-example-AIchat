#!/bin/bash
# Reset the database (WARNING: This will delete all data!)

set -e

# Navigate to backend directory
cd "$(dirname "$0")/.."

echo "WARNING: This will delete all data in the database!"
read -p "Are you sure you want to continue? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Database reset cancelled."
    exit 0
fi

echo "Activating virtual environment..."
source venv/bin/activate

echo "Resetting database..."
python3 -m src.infrastructure.database.init_db reset

echo ""
echo "Database reset complete!"

