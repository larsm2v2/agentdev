@echo off
REM Development startup script for Windows

echo 🚀 Starting Email Librarian Development Environment...

REM Stop any running containers
echo 📦 Stopping any existing containers...
docker-compose -f docker-compose.dev.yml down

REM Build the development image (this should be much faster)
echo 🔨 Building development image...
docker-compose -f docker-compose.dev.yml build email-librarian

REM Start all services
echo 🎯 Starting all services...
docker-compose -f docker-compose.dev.yml up -d

REM Wait a moment for services to start
timeout /t 5 /nobreak >nul

REM Show status
echo 📊 Service Status:
docker-compose -f docker-compose.dev.yml ps

echo.
echo ✅ Development environment ready!
echo 🌐 Frontend: http://localhost:8000
echo 🗄️  Database: localhost:5432
echo 🔍 Qdrant: http://localhost:6333
echo 🔄 n8n: http://localhost:5678
echo 📦 Redis: localhost:6379
echo.
echo 📝 To view logs: docker-compose -f docker-compose.dev.yml logs -f email-librarian
echo 🔄 Auto-reload is enabled - just edit your files and save!
