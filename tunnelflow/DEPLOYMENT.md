# 🚀 TunnelFlow - Deployment Guide

## Быстрый старт для тестового сервера

### Требования
- Docker 20.10+
- Docker Compose v2.0+
- 2GB+ RAM
- 10GB+ disk space
- Domain name (для SSL)

### 1. Подготовка сервера

```bash
# Обновление системы
sudo apt update && sudo apt upgrade -y

# Установка Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Установка Docker Compose (если не включен в Docker)
sudo apt install docker-compose-plugin -y

# Перелогиньтесь или выполните:
newgrp docker
```

### 2. Клонирование и настройка

```bash
cd /opt
git clone <your-repo-url> tunnelflow
cd tunnelflow

# Копирование конфига
cp .env.example .env

# Редактирование .env (ОБЯЗАТЕЛЬНО!)
nano .env
```

**Критические параметры для изменения в `.env`:**
```ini
POSTGRES_PASSWORD=YourSuperStrongPassword123!
SECRET_KEY=RandomSecretKeyGenerateWithOpenssl
STRIPE_SECRET_KEY=sk_live_...
BASE_DOMAIN=yourdomain.com
LETSENCRYPT_EMAIL=admin@yourdomain.com
```

### 3. Запуск

```bash
# Сделать скрипт исполняемым
chmod +x start.sh

# Запустить всё
./start.sh
```

### 4. Проверка

```bash
# Статус сервисов
docker compose ps

# Логи API
docker compose logs -f api

# Проверка базы данных
docker compose exec db psql -U tunnelflow -c "SELECT count(*) FROM users;"
```

### 5. Первый вход

1. Откройте `http://your-server-ip:8000/docs`
2. Создайте первого пользователя через POST `/api/v1/auth/register`
3. Войдите через POST `/api/v1/auth/login`
4. Получите JWT токен

### Production Checklist

- [ ] Изменены все пароли по умолчанию
- [ ] Настроен firewall (UFW/iptables)
- [ ] Включен SSL (Traefik автоматически)
- [ ] Настроено резервное копирование БД
- [ ] Настроен мониторинг алертов
- [ ] Ограничен доступ к админским панелям
- [ ] Настроен fail2ban
- [ ] Включен automatic security updates

### Резервное копирование

```bash
# Бэкап базы данных
docker compose exec db pg_dump -U tunnelflow tunnelflow > backup_$(date +%Y%m%d).sql

# Бэкап SSL сертификатов
tar -czf letsencrypt_backup.tar.gz ./letsencrypt

# Бэкап Redis данных
docker compose exec redis redis-cli SAVE
cp docker/redis/dump.rdb ./backup_dump_$(date +%Y%m%d).rdb
```

### Восстановление из бэкапа

```bash
# Восстановление БД
cat backup_20240514.sql | docker compose exec -T db psql -U tunnelflow tunnelflow

# Восстановление Redis
cp backup_dump_20240514.rdb docker/redis/dump.rdb
docker compose restart redis
```

### Мониторинг

**Grafana Dashboards:**
- http://localhost:3000 → Admin Dashboard
- Логин: `admin`, Пароль: из `.env` (по умолчанию `admin123`)

**Prometheus Metrics:**
- http://localhost:9090
- Query: `tunnelflow_active_connections`

### Troubleshooting

**API не запускается:**
```bash
docker compose logs api
# Проверьте DATABASE_URL и REDIS_URL в .env
```

**База данных не подключается:**
```bash
docker compose exec db pg_isready
# Проверьте POSTGRES_PASSWORD
```

**SSL не работает:**
```bash
docker compose logs traefik
# Убедитесь что домен указывает на IP сервера
# Порт 80 должен быть открыт для Let's Encrypt
```

### Обновление

```bash
# Pull новых образов
git pull
docker compose pull

# Пересоздание контейнеров
docker compose up -d --build

# Миграции БД (если есть)
docker compose exec api python -m tunnelflow.db.migrate
```

### Остановка

```bash
# Грациозная остановка
docker compose down

# Полное удаление (данные останутся в volumes)
docker compose down --volumes  # ОПАСНО: удалит все данные!
```

---

## Контакты поддержки

- GitHub Issues: [ссылка]
- Документация: http://localhost:8000/docs
- Email: support@tunnelflow.io
