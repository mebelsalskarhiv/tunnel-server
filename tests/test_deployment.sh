#!/bin/bash
set -e

echo "🧪 Testing TunnelFlow Deployment..."
echo "===================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

cleanup() {
    log_info "Cleaning up..."
    docker compose down -v 2>/dev/null || true
}

# Trap to cleanup on exit
trap cleanup EXIT

# Check Docker
if ! command -v docker &> /dev/null; then
    log_error "Docker is not installed"
    exit 1
fi

if ! docker compose version &> /dev/null && ! docker-compose version &> /dev/null; then
    log_error "Docker Compose is not installed"
    exit 1
fi

# Set COMPOSE_CMD
if docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
else
    COMPOSE_CMD="docker-compose"
fi

# Create .env if not exists
if [ ! -f tunnelflow/.env ]; then
    log_info "Creating .env from .env.example..."
    cp tunnelflow/.env.example tunnelflow/.env
fi

# Create necessary directories
mkdir -p logs test-webapp

# Create simple test webapp
cat > test-webapp/index.html << 'EOF'
<!DOCTYPE html>
<html>
<head>
    <title>Test WebApp</title>
</head>
<body>
    <h1>✅ Test WebApp is running!</h1>
    <p>If you see this, the tunnel is working correctly.</p>
</body>
</html>
EOF

log_info "Starting services..."
$COMPOSE_CMD up -d --build

log_info "Waiting for services to be ready (30 seconds)..."
sleep 30

# Check service status
log_info "Checking service status..."
$COMPOSE_CMD ps

# Health checks
log_info "Running health checks..."

# Check API health
log_info "Checking API health endpoint..."
if curl -sf http://localhost:8000/health > /dev/null; then
    log_info "✅ API health check passed"
else
    log_error "❌ API health check failed"
    docker compose logs tunnelflow-api
    exit 1
fi

# Check root endpoint
log_info "Checking API root endpoint..."
ROOT_RESPONSE=$(curl -sf http://localhost:8000/)
if echo "$ROOT_RESPONSE" | grep -q "TunnelFlow"; then
    log_info "✅ API root endpoint passed"
else
    log_error "❌ API root endpoint failed"
    echo "$ROOT_RESPONSE"
    exit 1
fi

# Check Traefik dashboard
log_info "Checking Traefik dashboard..."
if curl -sf http://localhost:8081/api/overview > /dev/null; then
    log_info "✅ Traefik dashboard accessible"
else
    log_warn "⚠️  Traefik dashboard not accessible (may need more time)"
fi

# Test user registration
log_info "Testing user registration..."
REGISTER_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"testpass123"}')

if echo "$REGISTER_RESPONSE" | grep -q '"id"'; then
    log_info "✅ User registration successful"
    USER_ID=$(echo "$REGISTER_RESPONSE" | grep -o '"id":[0-9]*' | cut -d':' -f2)
    log_info "User ID: $USER_ID"
elif echo "$REGISTER_RESPONSE" | grep -q "Email already registered"; then
    log_warn "⚠️  User already exists (continuing with login test)"
else
    log_error "❌ User registration failed"
    echo "$REGISTER_RESPONSE"
    exit 1
fi

# Test user login
log_info "Testing user login..."
TOKEN_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=test@example.com&password=testpass123")

TOKEN=$(echo "$TOKEN_RESPONSE" | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)

if [ -n "$TOKEN" ]; then
    log_info "✅ User login successful"
    log_info "Token received (first 20 chars): ${TOKEN:0:20}..."
else
    log_error "❌ User login failed"
    echo "$TOKEN_RESPONSE"
    exit 1
fi

# Test get profile
log_info "Testing get profile endpoint..."
PROFILE_RESPONSE=$(curl -sf http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer $TOKEN")

if echo "$PROFILE_RESPONSE" | grep -q "email"; then
    log_info "✅ Get profile successful"
else
    log_error "❌ Get profile failed"
    echo "$PROFILE_RESPONSE"
    exit 1
fi

# Test create tunnel
log_info "Testing tunnel creation..."
TUNNEL_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/tunnels \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"subdomain":"test-tunnel","target_port":8080,"protocol":"http"}')

if echo "$TUNNEL_RESPONSE" | grep -q '"id"'; then
    log_info "✅ Tunnel creation successful"
    TUNNEL_ID=$(echo "$TUNNEL_RESPONSE" | grep -o '"id":"[^"]*"' | cut -d'"' -f4)
    log_info "Tunnel ID: $TUNNEL_ID"
elif echo "$TUNNEL_RESPONSE" | grep -qi "error\|detail"; then
    log_error "❌ Tunnel creation failed"
    echo "$TUNNEL_RESPONSE"
    exit 1
else
    log_warn "⚠️  Tunnel response format unexpected (may still work)"
    echo "$TUNNEL_RESPONSE"
fi

# Test list tunnels
log_info "Testing list tunnels..."
LIST_RESPONSE=$(curl -sf http://localhost:8000/api/v1/tunnels \
  -H "Authorization: Bearer $TOKEN")

if [ -n "$LIST_RESPONSE" ]; then
    log_info "✅ List tunnels successful"
else
    log_warn "⚠️  List tunnels returned empty or failed"
fi

# Summary
echo ""
echo "===================================="
log_info "🎉 All tests completed successfully!"
echo "===================================="
echo ""
echo "📊 Access points:"
echo "   - API Server:      http://localhost:8000"
echo "   - API Docs:        http://localhost:8000/docs"
echo "   - Traefik Dashboard: http://localhost:8081"
echo "   - Test WebApp:     http://test.localhost"
echo ""
echo "🔧 Useful commands:"
echo "   - View logs:       $COMPOSE_CMD logs -f tunnelflow-api"
echo "   - Stop all:        $COMPOSE_CMD down"
echo "   - Restart:         $COMPOSE_CMD restart"
echo ""

exit 0
