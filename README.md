# Tunnel Server

**Версия:** 1.0.0

Сервер туннелей для проброса локальных сервисов через интернет (аналог ngrok).

## Возможности

- 🌐 Веб-интерфейс для управления клиентами и туннелями
- 🔐 Аутентификация клиентов по токенам
- 🚀 Автоматическое создание поддоменов в Traefik
- 🔒 Поддержка SSL/TLS через Let's Encrypt
- 📊 Статистика подключений и трафика
- 🐳 Docker Compose для быстрого развертывания

## Архитектура

```
Пользователь → Traefik (80/443) → Tunnel Server (8081) → Control Connection → Client → Local Service (localhost:3000)
```

1. **Traefik** - принимает HTTP/HTTPS запросы, определяет поддомен, проксирует на tunnel-server
2. **Tunnel Server** - управляет туннелями, проксирует запросы клиентам через control соединение
3. **Client** - подключается к серверу, получает запросы и проксирует на локальный сервис

## Требования

- Docker и Docker Compose
- Python 3.9+ (для клиента)
- Домен с настроенным DNS (для production) или localhost (для разработки)

## Установка

### 1. Клонирование репозитория

```bash
git clone <repository-url>
cd tunnel-server
```

### 2. Настройка переменных окружения

Создайте файл `.env` в корне проекта:

```bash
# Домен вашего сервера
DOMAIN=your-domain.com

# Email для Let's Encrypt
LETSENCRYPT_EMAIL=your-email@your-domain.com

# Включить SSL (true для production, false для localhost)
ENABLE_SSL=true
```

### 3. Запуск сервера

```bash
docker-compose up -d
```

Сервер будет доступен:
- Веб-интерфейс: `http://tunnel.localhost` (или `http://tunnel.your-domain.com`)
- Traefik Dashboard: `http://traefik.localhost:8080`

## Использование

### 1. Создание клиента

1. Откройте веб-интерфейс: `http://tunnel.localhost`
2. Перейдите в раздел "Clients"
3. Нажмите "Create Client"
4. Скопируйте конфигурационный файл (JSON)

### 2. Настройка клиента

Сохраните конфигурационный файл как `tunnel_config.json` на машине, где будет работать клиент.

Пример конфигурации:

```json
{
  "server": {
    "host": "your-domain.com",
    "control_port": 2222,
    "proxy_port": 2223,
    "domain": "your-domain.com"
  },
  "client": {
    "id": "your-client-id",
    "name": "My Client",
    "token": "your-token-here"
  },
  "tunnels": [
    {
      "subdomain": "myapp",
      "local_port": 3000,
      "local_host": "localhost",
      "protocol": "http"
    }
  ]
}
```

### 3. Установка зависимостей клиента

```bash
cd client
pip install -r requirements.txt
```

### 4. Запуск клиента

```bash
python tunnel_client.py tunnel_config.json
```

Клиент подключится к серверу и начнет проксировать запросы на локальный сервис.

### 5. Создание туннеля

1. В веб-интерфейсе перейдите в раздел "Tunnels"
2. Выберите клиента
3. Укажите поддомен (например, `myapp`)
4. Укажите локальный порт (например, `3000`)
5. Нажмите "Create Tunnel"

Туннель будет доступен по адресу: `http://myapp.your-domain.com` (или `http://myapp.localhost` для разработки)

## Конфигурация

### Переменные окружения сервера

- `TUNNEL_DOMAIN` - домен для туннелей (по умолчанию: `localhost`)
- `TUNNEL_CONTROL_PORT` - порт для control соединений (по умолчанию: `8080`)
- `TUNNEL_PROXY_PORT` - порт для proxy соединений (по умолчанию: `8081`)
- `TUNNEL_WEB_PORT` - порт веб-интерфейса (по умолчанию: `8082`)
- `ENABLE_SSL` - включить SSL через Let's Encrypt (по умолчанию: `false`)
- `DATABASE_URL` - URL базы данных (по умолчанию: `sqlite:///data/tunnel.db`)

### Порты

- `80` - HTTP (Traefik)
- `443` - HTTPS (Traefik)
- `2222` - Control порт для клиентов (Traefik → Tunnel Server)
- `8080` - Traefik Dashboard

## Разработка

### Локальная разработка

Для разработки используйте `localhost`:

1. В `.env` установите:
   ```bash
   DOMAIN=localhost
   ENABLE_SSL=false
   ```

2. Добавьте в `/etc/hosts` (Linux/Mac) или `C:\Windows\System32\drivers\etc\hosts` (Windows):
   ```
   127.0.0.1 tunnel.localhost
   127.0.0.1 traefik.localhost
   127.0.0.1 myapp.localhost
   ```

3. Запустите сервер:
   ```bash
   docker-compose up -d
   ```

### Структура проекта

```
tunnel-server/
├── client/                 # Клиент для подключения к серверу
│   ├── tunnel_client.py    # Основной код клиента
│   ├── requirements.txt   # Зависимости клиента
│   └── tunnel_config.json  # Пример конфигурации
├── server/                 # Сервер туннелей
│   ├── server.py          # Основной код сервера
│   ├── Dockerfile         # Docker образ сервера
│   ├── requirements.txt   # Зависимости сервера
│   ├── templates/         # HTML шаблоны
│   └── static/            # Статические файлы (CSS, JS)
├── traefik/               # Конфигурация Traefik
│   ├── traefik.yml        # Основная конфигурация
│   └── dynamic/           # Динамические конфигурации
├── data/                  # Данные (БД, сертификаты)
├── docker-compose.yml      # Docker Compose конфигурация
└── README.md              # Этот файл
```

## Исправленные проблемы

### Версия 1.0.0

#### Проблемы с Traefik и динамическими поддоменами
- ✅ Добавлен File Provider для Traefik с поддержкой динамических конфигураций
- ✅ Автоматическое создание конфигураций Traefik при создании туннелей
- ✅ Автоматическое удаление конфигураций при удалении туннелей
- ✅ Настроен Let's Encrypt для автоматической выдачи SSL сертификатов

#### Проблемы с архитектурой проксирования
- ✅ Исправлена архитектура: сервер отправляет запросы клиенту через control соединение
- ✅ Клиент проксирует запросы на локальный сервис и отправляет ответы обратно
- ✅ Поддержка клиентов за NAT

#### Проблемы с чтением данных
- ✅ Исправлено чтение больших сообщений от клиента (буферизация вместо readline)
- ✅ Улучшено чтение HTTP запросов с правильной обработкой Content-Length
- ✅ Улучшено чтение HTTP ответов с поддержкой chunked encoding
- ✅ Правильная обработка Connection: close

#### Проблемы с закрытием соединений
- ✅ Исправлено преждевременное закрытие соединений (Traefik получал "unexpected EOF")
- ✅ Добавлена задержка перед закрытием соединения для корректной работы с Traefik

## Логирование

### Сервер

```bash
docker-compose logs -f tunnel-server
```

### Traefik

```bash
docker-compose logs -f traefik
```

### Клиент

Клиент выводит логи в консоль. Для более детального логирования измените уровень в `tunnel_client.py`:

```python
logging.basicConfig(level=logging.DEBUG)
```

## Ограничения

- Максимальный размер ответа: 10MB (можно изменить в коде)
- Максимальный размер заголовков: 64KB
- Таймаут чтения ответа: 10 секунд (можно изменить в коде)

## Безопасность

- ⚠️ Токены клиентов хранятся в открытом виде в базе данных
- ⚠️ Для production рекомендуется использовать HTTPS
- ⚠️ Рекомендуется ограничить доступ к веб-интерфейсу

## Лицензия

MIT

## Автор

Разработано для внутреннего использования.

