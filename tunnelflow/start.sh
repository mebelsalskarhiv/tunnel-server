#!/bin/bash

# ===========================================
# TunnelFlow Quick Start Script
# ===========================================
# This script sets up and starts the entire TunnelFlow stack

set -e

echo "🚀 TunnelFlow - Quick Start"
echo "=========================="

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found. Creating from .env.example..."
    cp .env.example .env
    echo "✅ .env created. Please edit .env and set your passwords!"
    echo ""
    read -p "Press Enter after you've edited .env..." 
fi

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p logs ssl letsencrypt monitoring/grafana/dashboards monitoring/grafana/datasources

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

echo "🐳 Starting services with Docker Compose..."

# Use 'docker compose' (v2) or 'docker-compose' (v1)
if docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
else
    COMPOSE_CMD="docker-compose"
fi

# Start all services
$COMPOSE_CMD up -d --build

echo ""
echo "⏳ Waiting for services to be ready..."
sleep 15

# Check health of services
echo "🏥 Checking service health..."
$COMPOSE_CMD ps

echo ""
echo "✅ TunnelFlow is starting up!"
echo ""
echo "📊 Access points:"
echo "   - API Server:      http://localhost:8000"
echo "   - Traefik Dashboard: http://localhost:8080"
echo "   - Grafana:         http://localhost:3000 (admin/admin123)"
echo "   - Prometheus:      http://localhost:9090"
echo ""
echo "🔧 Useful commands:"
echo "   - View logs:       $COMPOSE_CMD logs -f api"
echo "   - Stop all:        $COMPOSE_CMD down"
echo "   - Restart:         $COMPOSE_CMD restart"
echo "   - Database backup: $COMPOSE_CMD exec db pg_dump -U tunnelflow tunnelflow > backup.sql"
echo ""
echo "📖 Next steps:"
echo "   1. Visit http://localhost:8000/docs to explore the API"
echo "   2. Register a new user account"
echo "   3. Create your first tunnel"
echo "   4. Download the client package"
echo ""
echo "⚠️  IMPORTANT: Change default passwords in .env before production use!"
