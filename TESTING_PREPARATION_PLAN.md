# TunnelFlow - План подготовки к тестированию

## 📋 Резюме текущего состояния

Проект находится в состоянии **незавершенного рефакторинга** от монолитной архитектуры (`server/server.py`) к модульной (`tunnelflow/`). Обнаружены две параллельные, несовместимые реализации одного и того же функционала.

---

## 🔴 Критические проблемы (блокируют тестирование)

### 1. Дублирование серверных реализаций
**Проблема:** Существуют два независимых сервера:
- `server/server.py` (1216 строк) - монолит на TCP сокетах с SQLite
- `tunnelflow/` (~800 строк) - модульная архитектура на WebSocket с PostgreSQL

**Решение:**
```bash
# Вариант А: Удалить старый server/ (рекомендуется)
rm -rf /workspace/server/

# Вариант Б: Переместить в archive/
mv /workspace/server/ /workspace/archive/legacy_server/
```

### 2. docker-compose.yml использует старую архитектуру
**Проблема:** Файл запускает `server/server.py` вместо `tunnelflow/main.py`

**Требуемые изменения:**
- Добавить сервисы: PostgreSQL, Redis
- Изменить сервис `tunnel-server` на `tunnelflow-api`
- Обновить порты и переменные окружения
- Добавить зависимости между сервисами

### 3. Несовместимые модели данных
**Проблема:** Разные схемы БД в `server/server.py` и `tunnelflow/db/models.py`:

| Аспект | server/server.py | tunnelflow/db/models.py |
|--------|------------------|-------------------------|
| Тип ID | UUID string | Integer autoincrement |
| Client model | Client | User |
| Tunnel model | Tunnel | Tunnel |
| Поля Tunnel | subdomain, client_id, local_port | user_id, subdomain, token_hash, ssl_enabled |
| Auth | Token string | JWT + password hash |

**Решение:** Использовать только модели из `tunnelflow/db/models.py`

### 4. Конфликт протоколов соединения
**Проблема:** 
- `server/server.py`: TCP сокеты (порт 8080)
- `tunnelflow/core/websocket_handler.py`: WebSocket (порт 8000)

**Решение:** Унифицировать на WebSocket (tunnelflow подход)

### 5. Отсутствуют критические сервисы
**Проблема:** В docker-compose нет:
- PostgreSQL (требуется в `tunnelflow/db/database.py`)
- Redis (требуется для pub/sub между HTTP proxy и WebSocket handler)

---

## 🟡 Проблемы средней важности

### 6. Неполная реализация HTTP проксирования
**Файл:** `tunnelflow/core/http_proxy.py`, строки 148-170

**Проблема:** Метод `wait_for_response()` возвращает mock-ответ вместо реальной реализации

**Код требует доработки:**
```python
async def wait_for_response(self, request_id: str, timeout: int = 30):
    # СЕЙЧАС: Заглушка
    # ТРЕБУЕТСЯ: Реализация через Redis pub/sub или asyncio.Future
```

### 7. Конфликт портов 8080
**Проблема:** 
- Traefik dashboard занимает порт 8080
- Старый server.py также использует порт 8080

**Решение:** Изменить порт Traefik dashboard на 8081 в `traefik/traefik.yml`

### 8. Missing imports в API routes
**Файл:** `tunnelflow/api/routes/tunnels.py`, строка 10

**Проблема:** Импорт `get_db_session` не существует
```python
from ..db.database import get_db_session  # ❌ Не существует
# Должно быть:
from ..db.database import get_db  # ✅
```

### 9. Несогласованность импортов
**Файл:** `tunnelflow/api/routes/auth.py`, строки 16-18

**Проблема:** Неправильные пути импорта:
```python
from ..db.database import get_db  # ❌ Должен быть абсолютный импорт
from ..db.models import User
from ..billing.plans import initialize_plans
```

### 10. Отсутствует Dockerfile для tunnelflow
**Проблема:** Есть только `server/Dockerfile` для старой версии

**Решение:** Создать `/workspace/tunnelflow/Dockerfile`

---

## 🟢 Минорные проблемы

### 11. Отсутствует .env.example
**Расположение:** `/workspace/tunnelflow/.env.example`

**Содержимое должно включать:**
```bash
DATABASE_URL=postgresql://tunnelflow:tunnelflow@db:5432/tunnelflow
REDIS_HOST=redis
REDIS_PORT=6379
SECRET_KEY=change-this-in-production
DEBUG=false
DOMAIN=localhost
ENABLE_SSL=false
```

### 12. Не настроен healthcheck для сервисов
**Файл:** `docker-compose.yml`

**Решение:** Добавить health checks для api, db, redis

---

## 📝 План действий по шагам

### Этап 1: Консолидация кодовой базы (Приоритет: КРИТИЧЕСКИЙ)

#### Шаг 1.1: Архивировать legacy код
```bash
mkdir -p /workspace/archive
mv /workspace/server /workspace/archive/legacy_server
mv /workspace/client /workspace/archive/legacy_client
```

#### Шаг 1.2: Исправить импорты в API routes
**Файлы:**
- `tunnelflow/api/routes/auth.py`
- `tunnelflow/api/routes/tunnels.py`
- `tunnelflow/api/routes/billing.py`
- `tunnelflow/api/routes/stats.py`

**Изменения:**
```python
# Было:
from ..db.database import get_db
from ..db.models import User

# Стало:
from tunnelflow.db.database import get_db
from tunnelflow.db.models import User
```

#### Шаг 1.3: Исправить tunnels.py
```python
# Строка 10:
from tunnelflow.db.database import get_db  # вместо get_db_session

# Строка 13:
from tunnelflow.api.routes.auth import get_current_user  # проверить TokenData
```

### Этап 2: Инфраструктура (Приоритет: КРИТИЧЕСКИЙ)

#### Шаг 2.1: Переписать docker-compose.yml

```yaml
services:
  traefik:
    image: traefik:v2.10
    container_name: traefik
    command:
      - --api.dashboard=true
      - --api.insecure=true
      - --providers.docker=true
      - --providers.docker.exposedbydefault=false
      - --providers.file.directory=/etc/traefik/dynamic
      - --entrypoints.web.address=:80
      - --entrypoints.websecure.address=:443
      - --entrypoints.tunnel-ws.address=:2222
    ports:
      - "80:80"
      - "443:443"
      - "2222:2222"
      - "8081:8080"  # Изменено с 8080:8080
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - ./traefik/dynamic:/etc/traefik/dynamic
    networks:
      - tunnel-network

  db:
    image: postgres:15-alpine
    container_name: tunnelflow-db
    environment:
      POSTGRES_DB: tunnelflow
      POSTGRES_USER: tunnelflow
      POSTGRES_PASSWORD: ${DB_PASSWORD:-tunnelflow}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - tunnel-network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U tunnelflow"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    container_name: tunnelflow-redis
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    networks:
      - tunnel-network
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  tunnelflow-api:
    build:
      context: ./tunnelflow
      dockerfile: Dockerfile
    container_name: tunnelflow-api
    environment:
      - DATABASE_URL=postgresql://tunnelflow:${DB_PASSWORD:-tunnelflow}@db:5432/tunnelflow
      - REDIS_HOST=redis
      - REDIS_PORT=6379
      - SECRET_KEY=${SECRET_KEY:-change-this-in-production}
      - DEBUG=${DEBUG:-false}
      - DOMAIN=${DOMAIN:-localhost}
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ./tunnelflow:/app
      - ./logs:/app/logs
    networks:
      - tunnel-network
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.tunnelflow-api.rule=Host(`api.${DOMAIN:-localhost}`)"
      - "traefik.http.routers.tunnelflow-api.entrypoints=web"
      - "traefik.http.services.tunnelflow-api.loadbalancer.server.port=8000"
      
      # WebSocket endpoint для туннелей
      - "traefik.http.routers.tunnel-ws.rule=PathPrefix(`/ws/tunnel`)"
      - "traefik.http.routers.tunnel-ws.entrypoints=tunnel-ws"
      - "traefik.http.services.tunnel-ws.loadbalancer.server.port=8000"
      
      # HTTP proxy для трафика туннелей
      - "traefik.http.routers.tunnel-proxy.rule=HostRegexp(`{subdomain:[a-z0-9-]+}.${DOMAIN:-localhost}`)"
      - "traefik.http.routers.tunnel-proxy.entrypoints=web"
      - "traefik.http.services.tunnel-proxy.loadbalancer.server.port=8000"

  test-webapp:
    image: nginx:alpine
    container_name: test-webapp
    volumes:
      - ./test-webapp:/usr/share/nginx/html
    networks:
      - tunnel-network
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.test-webapp.rule=Host(`test.${DOMAIN:-localhost}`)"
      - "traefik.http.routers.test-webapp.entrypoints=web"

networks:
  tunnel-network:
    driver: bridge

volumes:
  postgres_data:
  redis_data:
```

#### Шаг 2.2: Создать Dockerfile для tunnelflow

**Файл:** `/workspace/tunnelflow/Dockerfile`
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Копирование зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование исходного кода
COPY . .

# Создание директорий
RUN mkdir -p logs

# Порт FastAPI приложения
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health')" || exit 1

# Запуск приложения
CMD ["uvicorn", "tunnelflow.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### Шаг 2.3: Создать .env.example

**Файл:** `/workspace/tunnelflow/.env.example`
```bash
# Database
DB_PASSWORD=tunnelflow_secure_password_change_me

# Application
SECRET_KEY=your-secret-key-min-32-characters-long
DEBUG=false
DOMAIN=localhost
ENABLE_SSL=false

# Let's Encrypt (для продакшена)
LETSENCRYPT_EMAIL=admin@example.com
```

### Этап 3: Исправление кода (Приоритет: ВЫСОКИЙ)

#### Шаг 3.1: Реализовать Redis pub/sub для HTTP proxy

**Файл:** `tunnelflow/core/http_proxy.py`

Добавить интеграцию с Redis для ожидания ответов от клиентов.

#### Шаг 3.2: Исправить auth.py импорты

**Файл:** `tunnelflow/api/routes/auth.py`
```python
# Заменить относительные импорты на абсолютные
from tunnelflow.db.database import get_db
from tunnelflow.db.models import User
from tunnelflow.billing.plans import initialize_plans, get_user_plan, get_user_limits, get_current_usage
```

#### Шаг 3.3: Добавить missing функции в billing/plans.py

Проверить наличие функций:
- `get_user_plan()`
- `get_user_limits()`
- `get_current_usage()`

### Этап 4: Тестирование (Приоритет: СРЕДНИЙ)

#### Шаг 4.1: Создать тестовый скрипт

**Файл:** `/workspace/tests/test_deployment.sh`
```bash
#!/bin/bash
set -e

echo "🧪 Testing TunnelFlow Deployment..."

# 1. Проверка запуска сервисов
docker compose up -d --build
sleep 30

# 2. Health checks
curl -f http://localhost:8000/health || exit 1
curl -f http://localhost:8081/api/ || exit 1

# 3. Тест регистрации пользователя
RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"testpass123"}')

echo "$RESPONSE" | grep -q "id" || exit 1

# 4. Тест входа
TOKEN_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=test@example.com&password=testpass123")

TOKEN=$(echo "$TOKEN_RESPONSE" | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)

if [ -z "$TOKEN" ]; then
  echo "❌ Failed to get access token"
  exit 1
fi

# 5. Тест создания туннеля
TUNNEL_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/tunnels \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"subdomain":"test-tunnel","target_port":8080}')

echo "$TUNNEL_RESPONSE" | grep -q "id" || exit 1

echo "✅ All tests passed!"
docker compose down
```

#### Шаг 4.2: Создать README для тестирования

**Файл:** `/workspace/TESTING_GUIDE.md`

---

## ✅ Чеклист готовности к тестированию

- [ ] Legacy код архивирован
- [ ] docker-compose.yml переписан для tunnelflow
- [ ] PostgreSQL и Redis добавлены в compose
- [ ] Dockerfile создан для tunnelflow
- [ ] .env.example создан
- [ ] Все импорты в API routes исправлены
- [ ] Redis pub/sub интегрирован в HTTP proxy
- [ ] Health checks настроены
- [ ] Тестовый скрипт создан
- [ ] Документация обновлена

---

## 📊 Оценка времени

| Этап | Время | Приоритет |
|------|-------|-----------|
| Этап 1: Консолидация | 2-3 часа | КРИТИЧЕСКИЙ |
| Этап 2: Инфраструктура | 3-4 часа | КРИТИЧЕСКИЙ |
| Этап 3: Исправление кода | 4-6 часов | ВЫСОКИЙ |
| Этап 4: Тестирование | 2-3 часа | СРЕДНИЙ |
| **Итого** | **11-16 часов** | |

---

## 🚀 Быстрый старт после исправлений

```bash
# 1. Клонировать .env из example
cd tunnelflow
cp .env.example .env
nano .env  # Отредактировать пароли

# 2. Запустить все сервисы
docker compose up -d --build

# 3. Проверить логи
docker compose logs -f tunnelflow-api

# 4. Открыть API документы
open http://localhost:8000/docs

# 5. Запустить тесты
./tests/test_deployment.sh
```

---

**Дата составления плана:** $(date +%Y-%m-%d)  
**Статус:** Готов к выполнению  
**Ответственный:** AI Assistant
