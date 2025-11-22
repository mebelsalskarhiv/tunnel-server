# PowerShell скрипт для настройки Git и отправки на GitHub

Write-Host "=== Настройка Git репозитория ===" -ForegroundColor Green

# Инициализация репозитория
if (-not (Test-Path .git)) {
    Write-Host "Инициализация Git репозитория..." -ForegroundColor Yellow
    git init
} else {
    Write-Host "Git репозиторий уже инициализирован" -ForegroundColor Green
}

# Добавление файлов
Write-Host "Добавление файлов..." -ForegroundColor Yellow
git add .

# Проверка статуса
Write-Host ""
Write-Host "=== Статус репозитория ===" -ForegroundColor Green
git status

Write-Host ""
Write-Host "=== Следующие шаги ===" -ForegroundColor Cyan
Write-Host "1. Создайте репозиторий на GitHub: https://github.com/new" -ForegroundColor White
Write-Host "2. Выполните команды:" -ForegroundColor White
Write-Host "   git commit -m 'Initial commit: Tunnel Server v1.0.0'" -ForegroundColor Yellow
Write-Host "   git remote add origin https://github.com/mebelsalskarhiv/tunnel-server.git" -ForegroundColor Yellow
Write-Host "   git push -u origin main" -ForegroundColor Yellow
Write-Host ""
Write-Host "Или используйте инструкции из GITHUB_SETUP.md" -ForegroundColor White

