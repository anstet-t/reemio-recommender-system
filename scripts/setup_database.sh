#!/bin/bash
# =============================================================================
# Database Setup Script
# Sets up PostgreSQL with pgvector extension
# =============================================================================

set -e

echo "Setting up PostgreSQL with pgvector for Reemio Recommender System..."

# Check required environment variables
if [ -z "$POSTGRES_HOST" ]; then
    POSTGRES_HOST="localhost"
fi

if [ -z "$POSTGRES_PORT" ]; then
    POSTGRES_PORT="5432"
fi

if [ -z "$POSTGRES_USER" ]; then
    echo "Error: POSTGRES_USER environment variable is not set."
    exit 1
fi

if [ -z "$POSTGRES_DB" ]; then
    POSTGRES_DB="reemio_recommender"
fi

echo "Database: $POSTGRES_HOST:$POSTGRES_PORT/$POSTGRES_DB"

# Create pgvector extension
echo "Creating pgvector extension..."
PGPASSWORD=$POSTGRES_PASSWORD psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" <<EOF
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Verify installation
SELECT extversion FROM pg_extension WHERE extname = 'vector';
EOF

echo ""
echo "pgvector setup complete!"
echo ""
echo "Next steps:"
echo "  1. Run database migrations: alembic upgrade head"
echo "  2. Seed sample data: python scripts/seed_data.py"
