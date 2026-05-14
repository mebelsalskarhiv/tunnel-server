# TunnelFlow - Professional Tunneling Platform v2.0

## 📋 Overview

**TunnelFlow** is a modern tunneling platform (like ngrok) with billing, monitoring, and user-friendly client packages.

### Key Features
- ✅ HTTP/HTTPS tunnels via custom domains and server subdomains
- ✅ Billing system with 5 tariff plans (Free to Enterprise)
- ✅ Real-time monitoring dashboard for admins and users
- ✅ Auto-generated client packages (.bat/.sh scripts)
- ✅ JWT authentication and token hashing
- ✅ PostgreSQL + Redis for data and metrics
- ✅ FastAPI backend + React frontend ready

---

## 🏗️ Architecture

```
tunnelflow/
├── main.py                 # FastAPI application entry point
├── core/                   # Core tunneling logic
├── api/                    # REST API endpoints
│   ├── routes/
│   │   ├── auth.py        # Registration, login, JWT
│   │   ├── billing.py     # Plans, invoices, payments
│   │   └── stats.py       # Real-time metrics
│   └── middleware/         # Auth, rate limiting
├── db/                     # Database layer
│   ├── models.py          # SQLAlchemy ORM models
│   └── database.py        # DB connection management
├── billing/                # Billing system
│   └── plans.py           # Tariff plans and limits
├── monitoring/             # Monitoring & metrics
│   └── metrics.py         # Real-time stats collection
├── client_generator/       # Client package generator
│   └── packager.py        # ZIP package creation
└── config/                 # Configuration files
```

---

## 💰 Tariff Plans

| Plan | Price | Tunnels | Traffic/Month | Custom Domains | Subdomains |
|------|-------|---------|---------------|----------------|------------|
| **Free** | $0 | 1 | 1 GB | 0 | 1 |
| **Starter** | $5 | 3 | 20 GB | 1 | 3 |
| **Pro** | $15 | 10 | 100 GB | 5 | 10 |
| **Business** | $50 | 50 | 500 GB | 20 | 50 |
| **Enterprise** | Custom | Unlimited | Unlimited | Unlimited | Unlimited |

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- PostgreSQL 15+
- Redis 7+

### Installation

```bash
# Clone repository
cd /workspace/tunnelflow

# Install dependencies
pip install fastapi uvicorn sqlalchemy psycopg2-binary redis pyjwt python-multipart

# Set environment variables
export DATABASE_URL="postgresql://user:password@localhost:5432/tunnelflow"
export REDIS_HOST="localhost"
export SECRET_KEY="your-secret-key-here"

# Run the server
python -m tunnelflow.main
```

### API Documentation

After starting the server, access:
- Swagger UI: http://localhost:8000/api/docs
- ReDoc: http://localhost:8000/api/redoc
- Health check: http://localhost:8000/health

---

## 📦 Client Package Generator

Generate ready-to-use client packages for users:

```python
from tunnelflow.client_generator.packager import ClientPackageGenerator

generator = ClientPackageGenerator(
    base_domain="tunnelflow.io",
    server_host="tunnel.tunnelflow.io"
)

zip_path = generator.generate_package(
    tunnel_id=123,
    tunnel_name="My App",
    token="secret-token",
    local_port=8080,
    subdomain="myapp",
    output_dir="./packages",
    platform="all",  # windows, linux, macos, all
    include_client_binary=True,
)

print(f"Package created: {zip_path}")
```

### Inside the Package
- `tunnel_client.exe` - Client binary
- `config.json` - Pre-configured settings
- `run.bat` / `run.sh` - Launch script with menu
- `README.txt` - User instructions

---

## 🔌 API Endpoints

### Authentication
- `POST /api/v1/auth/register` - Register new user
- `POST /api/v1/auth/login` - Login (returns JWT)
- `GET /api/v1/auth/me` - Get current user profile

### Billing
- `GET /api/v1/billing/plans` - List available plans
- `GET /api/v1/billing/my-plan` - Get current plan & usage
- `GET /api/v1/billing/invoices` - Invoice history
- `POST /api/v1/billing/invoices/{id}/pay` - Pay invoice
- `POST /api/v1/billing/subscribe/{plan_id}` - Subscribe to plan

### Statistics
- `GET /api/v1/stats/global` - Global platform stats (admin)
- `GET /api/v1/stats/user/me` - User detailed stats
- `GET /api/v1/stats/user/me/realtime` - Real-time user metrics
- `GET /api/v1/stats/server/realtime` - Server real-time metrics
- `GET /api/v1/stats/server/history` - Server metrics history

---

## 📊 Monitoring

### Real-time Metrics (Redis)
- Active connections
- Requests per second (RPS)
- Traffic (bytes in/out per second)
- CPU/Memory usage
- Online tunnels and users

### Historical Stats (PostgreSQL)
- Daily traffic per user
- Request counts
- Top IPs
- Tunnel usage patterns

---

## 🔒 Security

- JWT tokens for API authentication (30-day expiry)
- Password hashing with SHA256 + salt
- Tunnel token hashing (never stored in plain text)
- Rate limiting (to be implemented)
- HTTPS required in production

---

## 🛠️ Development

### Project Structure
```
/workspace/
├── tunnelflow/          # New modular server (v2.0)
├── server/              # Legacy server.py (v1.0)
├── client/              # Legacy Python client
├── docker-compose.yml   # Docker setup
└── TUNNELFLOW_PLAN.md   # Full development plan
```

### Running Tests
```bash
pytest tests/ -v
```

### Docker Deployment
```bash
docker-compose up -d
```

---

## 📈 Roadmap

### Phase 1: Foundation (Weeks 1-2) ✅
- [x] Modular architecture
- [x] Database models
- [x] JWT authentication
- [x] Billing system
- [ ] Tunnel core logic

### Phase 2: Dashboard (Weeks 3-4)
- [ ] React frontend
- [ ] User dashboard
- [ ] Real-time charts
- [ ] Domain management

### Phase 3: Client (Week 5)
- [ ] Go client implementation
- [ ] Auto-reconnect logic
- [ ] Service installation

### Phase 4: Monitoring (Week 6)
- [ ] Admin dashboard
- [ ] Alert system
- [ ] Prometheus integration

### Phase 5: Polish (Week 7)
- [ ] Load testing
- [ ] Documentation
- [ ] CI/CD pipeline
- [ ] Production deployment

---

## 📝 License

MIT License - See LICENSE file for details

---

**Version:** 2.0.0  
**Status:** In Development  
**Contact:** support@tunnelflow.io
