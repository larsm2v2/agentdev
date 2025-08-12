#!/bin/bash
set -e

# Initialize databases for Email Librarian system
echo "Setting up additional databases..."

# Create n8n database for workflow automation
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE DATABASE n8n;
    GRANT ALL PRIVILEGES ON DATABASE n8n TO $POSTGRES_USER;
EOSQL

echo "✅ n8n database created and configured successfully!"
