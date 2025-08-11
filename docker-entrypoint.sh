#!/bin/bash

# Email Librarian Docker Entrypoint Script
set -e

echo "🐳 Starting Email Librarian Docker Container..."

# Function to wait for service
wait_for_service() {
    local host=$1
    local port=$2
    local service_name=$3
    
    echo "⏳ Waiting for $service_name at $host:$port..."
    
    while ! nc -z $host $port; do
        sleep 2
    done
    
    echo "✅ $service_name is ready!"
}

# Wait for dependent services
wait_for_service "$POSTGRES_HOST" "$POSTGRES_PORT" "PostgreSQL"
wait_for_service "$QDRANT_HOST" "$QDRANT_PORT" "Qdrant"
wait_for_service "redis" "6379" "Redis"

# Create necessary directories
echo "🔧 Creating required directories..."
mkdir -p logs data email_cache

echo "✅ Initialization complete!"

# Start the main application
echo "🚀 Starting Email Librarian Server..."
exec "$@"
