FROM python:3.14.3-alpine

WORKDIR /app

# Установка зависимостей
RUN apk add --no-cache sqlite

# Копирование requirements и установка Python пакетов
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Создание структуры директорий
RUN mkdir -p /app/templates /app/static/css /app/static/js /app/static/images /app/data

# Копирование исходного кода
COPY . .

# Открытие портов
EXPOSE 8080 8081 8082

CMD ["python", "server.py"]