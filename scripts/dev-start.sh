#!/bin/bash
# Development startup script

echo "🚀 Starting Email Librarian Development Environment..."

# Stop any running containers
echo "📦 Stopping any existing containers..."
docker-compose -f docker-compose.dev.yml down

# Build the development image (this should be much faster)
echo "🔨 Building development image..."
docker-compose -f docker-compose.dev.yml build email-librarian

# Start all services
echo "🎯 Starting all services..."
docker-compose -f docker-compose.dev.yml up -d

# Wait a moment for services to start
sleep 5

# Show status
echo "📊 Service Status:"
docker-compose -f docker-compose.dev.yml ps

echo ""
echo "✅ Development environment ready!"
echo "🌐 Frontend: http://localhost:8000"
echo "🗄️  Database: localhost:5432"
echo "🔍 Qdrant: http://localhost:6333"
echo "🔄 n8n: http://localhost:5678"
echo "📦 Redis: localhost:6379"
echo ""
echo "📝 To view logs: docker-compose -f docker-compose.dev.yml logs -f email-librarian"
echo "🔄 Auto-reload is enabled - just edit your files and save!"
