# TunnelFlow v2.0

Secure HTTP/HTTPS tunneling service with billing, monitoring, and client management.

## 🚀 Features

- **HTTP/HTTPS Tunnels** - Secure tunneling via subdomains and custom domains
- **Billing System** - Multi-tier subscription plans with usage tracking
- **Real-time Monitoring** - Live dashboards for users and administrators
- **Client Packages** - Auto-generated ZIP packages with run scripts
- **JWT Authentication** - Secure user authentication and authorization
- **Auto-reconnect** - Client-side exponential backoff reconnection

## 📦 Installation

### Prerequisites
- Python 3.9+
- PostgreSQL 14+
- Redis 7+

### Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env with your settings

# Initialize database
python -m tunnelflow.db.database

# Run server
python -m tunnelflow.main
```

## 🏗️ Architecture

```
tunnelflow/
├── main.py                 # FastAPI application entry point
├── api/
│   └── routes/
│       ├── auth.py         # Authentication endpoints
│       ├── billing.py      # Billing & subscriptions
│       ├── stats.py        # Statistics & monitoring
│       └── tunnels.py      # Tunnel management
├── core/
│   ├── tunnel_manager.py   # Tunnel lifecycle management
│   ├── websocket_handler.py # WebSocket connections
│   └── http_proxy.py       # HTTP request routing
├── db/
│   ├── models.py           # SQLAlchemy ORM models
│   └── database.py         # Database connection
├── billing/
│   └── plans.py            # Subscription plans & limits
├── monitoring/
│   └── metrics.py          # Real-time metrics collection
├── client_generator/
│   └── packager.py         # Client package generator
└── client/
    ├── client.py           # Tunnel client
    ├── run.bat             # Windows launcher
    └── run.sh              # Linux/macOS launcher
```

## 💰 Subscription Plans

| Plan | Price | Tunnels | Traffic | Custom Domains |
|------|-------|---------|---------|----------------|
| Free | $0 | 1 | 1 GB/mo | 0 |
| Starter | $5/mo | 3 | 20 GB/mo | 1 |
| Pro | $15/mo | 10 | 100 GB/mo | 5 |
| Business | $50/mo | 50 | 500 GB/mo | 20 |
| Enterprise | Custom | Unlimited | Unlimited | Unlimited |

## 🔌 API Endpoints

### Authentication
- `POST /api/auth/register` - Register new user
- `POST /api/auth/login` - Login and get JWT token
- `GET /api/auth/me` - Get current user profile

### Tunnels
- `GET /api/tunnels` - List user's tunnels
- `POST /api/tunnels` - Create new tunnel
- `GET /api/tunnels/{id}` - Get tunnel details
- `DELETE /api/tunnels/{id}` - Delete tunnel
- `POST /api/tunnels/{id}/regenerate-token` - Regenerate auth token
- `GET /api/tunnels/{id}/stats` - Get tunnel statistics

### Billing
- `GET /api/billing/plans` - List available plans
- `GET /api/billing/subscription` - Get current subscription
- `POST /api/billing/subscribe` - Subscribe to a plan
- `GET /api/billing/invoices` - List invoices
- `POST /api/billing/invoices/{id}/download` - Download invoice PDF

### Statistics
- `GET /api/stats/user` - User's usage statistics
- `GET /api/stats/server` - Server-wide statistics (admin)
- `WS /ws/tunnel` - WebSocket endpoint for clients

## 🖥️ Client Usage

### Generate Client Package

Via API:
```bash
curl -X POST http://localhost:8000/api/client/generate \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"tunnel_id": "your-tunnel-id"}' \
  --output tunnel-package.zip
```

### Run Client

**Windows:**
```cmd
unzip tunnel-package.zip
cd tunnel-package
run.bat
```

**Linux/macOS:**
```bash
unzip tunnel-package.zip
cd tunnel-package
chmod +x run.sh
./run.sh
```

### Manual Configuration

Create `config.json`:
```json
{
  "server_url": "https://tunnelflow.io",
  "tunnel_id": "your-tunnel-id",
  "client_token": "your-auth-token",
  "local_host": "localhost",
  "local_port": 8080,
  "heartbeat_interval": 30
}
```

Run:
```bash
python client.py --config config.json
```

## 📊 Monitoring

### User Dashboard
- Real-time traffic graphs
- Active connections count
- Monthly usage vs limits
- Tunnel status indicators

### Admin Dashboard
- Server CPU/Memory usage
- Total active tunnels
- Network throughput
- User activity heatmap
- Revenue metrics

## 🔒 Security

- JWT-based authentication
- Password hashing with bcrypt
- Token regeneration capability
- Rate limiting on API endpoints
- HTTPS enforcement in production

## 🛠️ Development

```bash
# Run tests
pytest

# Code formatting
black tunnelflow/

# Linting
flake8 tunnelflow/

# Run with auto-reload
uvicorn tunnelflow.main:app --reload
```

## 📝 License

MIT License - See LICENSE file for details.

## 🤝 Support

For issues and feature requests, please open an issue on GitHub.
