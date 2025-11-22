#!/bin/bash
# Скрипт для настройки Git и отправки на GitHub

echo "=== Настройка Git репозитория ==="

# Инициализация репозитория
if [ ! -d .git ]; then
    echo "Инициализация Git репозитория..."
    git init
else
    echo "Git репозиторий уже инициализирован"
fi

# Добавление файлов
echo "Добавление файлов..."
git add .

# Проверка статуса
echo ""
echo "=== Статус репозитория ==="
git status

echo ""
echo "=== Следующие шаги ==="
echo "1. Создайте репозиторий на GitHub: https://github.com/new"
echo "2. Выполните команды:"
echo "   git commit -m 'Initial commit: Tunnel Server v1.0.0'"
echo "   git remote add origin https://github.com/mebelsalskarhiv/tunnel-server.git"
echo "   git push -u origin main"
echo ""
echo "Или используйте команды из GITHUB_SETUP.md"

