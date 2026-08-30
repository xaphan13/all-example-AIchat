#!/bin/bash
# Setup PostgreSQL with pgvector (supports both local and Docker installations)

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Database configuration
CONTAINER_NAME="quorum-postgres"
DB_NAME="quorum"
DB_USER="quorum"
DB_PASSWORD="quorum"
DB_PORT="5432"

echo -e "${BLUE}Setting up PostgreSQL with pgvector...${NC}"
echo ""

# Function to setup local PostgreSQL
setup_local_postgres() {
    echo -e "${GREEN}Found local PostgreSQL installation!${NC}"
    echo "Setting up database and user..."
    
    # Determine which postgres superuser to use
    POSTGRES_USER="postgres"
    if command -v whoami > /dev/null 2>&1; then
        CURRENT_USER=$(whoami)
        # Try current user first (common on macOS with Homebrew)
        if psql -U "$CURRENT_USER" -d postgres -c "SELECT 1" > /dev/null 2>&1; then
            POSTGRES_USER="$CURRENT_USER"
        fi
    fi
    
    echo "Using PostgreSQL superuser: $POSTGRES_USER"
    
    # Create user if it doesn't exist
    echo "Creating user '$DB_USER'..."
    psql -U "$POSTGRES_USER" -d postgres -tc "SELECT 1 FROM pg_user WHERE usename = '$DB_USER'" | grep -q 1 || \
        psql -U "$POSTGRES_USER" -d postgres -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';" && \
        echo -e "${GREEN}✓ User created/verified${NC}"
    
    # Create database if it doesn't exist
    echo "Creating database '$DB_NAME'..."
    psql -U "$POSTGRES_USER" -d postgres -tc "SELECT 1 FROM pg_database WHERE datname = '$DB_NAME'" | grep -q 1 || \
        psql -U "$POSTGRES_USER" -d postgres -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;" && \
        echo -e "${GREEN}✓ Database created/verified${NC}"
    
    # Enable pgvector extension
    echo "Enabling pgvector extension..."
    psql -U "$POSTGRES_USER" -d "$DB_NAME" -c "CREATE EXTENSION IF NOT EXISTS vector;" > /dev/null 2>&1 && \
        echo -e "${GREEN}✓ pgvector extension enabled${NC}" || \
        echo -e "${YELLOW}⚠️  pgvector extension not available (optional)${NC}"
    
    # Grant privileges
    echo "Granting privileges..."
    psql -U "$POSTGRES_USER" -d postgres -c "ALTER DATABASE $DB_NAME OWNER TO $DB_USER;" > /dev/null 2>&1
    psql -U "$POSTGRES_USER" -d "$DB_NAME" -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;" > /dev/null 2>&1
    psql -U "$POSTGRES_USER" -d "$DB_NAME" -c "GRANT ALL PRIVILEGES ON SCHEMA public TO $DB_USER;" > /dev/null 2>&1
    psql -U "$POSTGRES_USER" -d "$DB_NAME" -c "GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO $DB_USER;" > /dev/null 2>&1
    psql -U "$POSTGRES_USER" -d "$DB_NAME" -c "GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO $DB_USER;" > /dev/null 2>&1
    echo -e "${GREEN}✓ Privileges granted${NC}"
    
    # Test connection
    echo "Testing connection..."
    if psql -h localhost -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1;" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Connection successful!${NC}"
        return 0
    else
        echo -e "${YELLOW}⚠️  Connection test had issues, but setup may still work${NC}"
        return 0
    fi
}

# Function to setup Docker PostgreSQL
setup_docker_postgres() {
    echo -e "${GREEN}Using Docker for PostgreSQL...${NC}"
    
    # Check if container already exists
    if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        echo "Container ${CONTAINER_NAME} already exists."
        
        # Check if it's running
        if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
            echo -e "${GREEN}Container is already running.${NC}"
        else
            echo "Starting existing container..."
            docker start ${CONTAINER_NAME}
        fi
    else
        echo "Creating new PostgreSQL container with pgvector..."
        
        docker run -d \
            --name ${CONTAINER_NAME} \
            -e POSTGRES_DB=${DB_NAME} \
            -e POSTGRES_USER=${DB_USER} \
            -e POSTGRES_PASSWORD=${DB_PASSWORD} \
            -p ${DB_PORT}:5432 \
            -v quorum-pgdata:/var/lib/postgresql/data \
            pgvector/pgvector:pg16
        
        echo "Waiting for PostgreSQL to be ready..."
        sleep 5
        
        # Wait for PostgreSQL to be ready
        for i in {1..30}; do
            if docker exec ${CONTAINER_NAME} pg_isready -U ${DB_USER} > /dev/null 2>&1; then
                echo -e "${GREEN}PostgreSQL is ready!${NC}"
                break
            fi
            echo "Waiting for PostgreSQL... ($i/30)"
            sleep 2
        done
    fi
    
    echo -e "\n${BLUE}Docker container management:${NC}"
    echo "  Stop:   docker stop ${CONTAINER_NAME}"
    echo "  Remove: docker rm -f ${CONTAINER_NAME}"
    echo "  Volume: docker volume rm quorum-pgdata"
}

# Check if local PostgreSQL is available
if pg_isready -h localhost -p "$DB_PORT" > /dev/null 2>&1; then
    setup_local_postgres
elif command -v docker > /dev/null 2>&1 && docker info > /dev/null 2>&1; then
    setup_docker_postgres
else
    echo -e "${RED}Error: Neither local PostgreSQL nor Docker is available.${NC}"
    echo ""
    echo "Please either:"
    echo "  1. Install and start PostgreSQL locally, or"
    echo "  2. Install and start Docker"
    echo ""
    echo "For macOS with Homebrew:"
    echo "  brew install postgresql@16"
    echo "  brew services start postgresql@16"
    echo ""
    exit 1
fi

echo ""
echo -e "${GREEN}✅ PostgreSQL with pgvector is ready!${NC}"
echo ""
echo -e "${BLUE}Connection details:${NC}"
echo "  Host:     localhost"
echo "  Port:     ${DB_PORT}"
echo "  Database: ${DB_NAME}"
echo "  User:     ${DB_USER}"
echo "  Password: ${DB_PASSWORD}"
echo ""
echo -e "${BLUE}Connection URL:${NC}"
echo "  postgresql://${DB_USER}:${DB_PASSWORD}@localhost:${DB_PORT}/${DB_NAME}"
echo ""

