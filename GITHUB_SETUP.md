# Инструкция по отправке на GitHub

## Подготовка к отправке

### 1. Проверка текущего состояния Git

```bash
# Проверяем, есть ли уже git репозиторий
git status
```

Если репозиторий не инициализирован, выполните:

```bash
# Инициализация репозитория
git init

# Настройка пользователя (если еще не настроено глобально)
git config user.name "Your Name"
git config user.email "your.email@example.com"
```

### 2. Добавление файлов

```bash
# Добавляем все файлы (кроме тех, что в .gitignore)
git add .

# Проверяем, что будет добавлено
git status
```

### 3. Создание первого коммита

```bash
# Создаем коммит с описанием версии
git commit -m "Initial commit: Tunnel Server v1.0.0

- Веб-интерфейс для управления клиентами и туннелями
- Автоматическое создание поддоменов в Traefik
- Поддержка SSL/TLS через Let's Encrypt
- Исправлена архитектура проксирования для клиентов за NAT
- Улучшено чтение HTTP запросов/ответов
- Исправлены проблемы с закрытием соединений"
```

### 4. Создание репозитория на GitHub

1. Перейдите на https://github.com/new
2. Заполните:
   - **Repository name**: `tunnel-server` (или другое имя)
   - **Description**: "Tunnel server for exposing local services to the internet"
   - **Visibility**: Private или Public (на ваше усмотрение)
   - **НЕ** добавляйте README, .gitignore или license (они уже есть)
3. Нажмите "Create repository"

### 5. Подключение к GitHub

```bash
# Добавляем remote (замените mebelsalskarhiv на ваш GitHub username)
git remote add origin https://github.com/mebelsalskarhiv/tunnel-server.git

# Или если используете SSH:
# git remote add origin git@github.com:mebelsalskarhiv/tunnel-server.git

# Проверяем remote
git remote -v
```

### 6. Отправка на GitHub

```bash
# Отправляем код на GitHub (первый раз)
git push -u origin main

# Если ваша ветка называется master, используйте:
# git push -u origin master
```

Если GitHub попросит авторизацию:
- Для HTTPS: используйте Personal Access Token (не пароль)
- Для SSH: убедитесь, что SSH ключ добавлен в GitHub

### 7. Создание тега версии (опционально)

```bash
# Создаем тег для версии 1.0.0
git tag -a v1.0.0 -m "Version 1.0.0 - Initial release"

# Отправляем теги на GitHub
git push origin v1.0.0
```

## Дальнейшая работа

### Создание новой ветки для разработки

```bash
# Создаем и переключаемся на новую ветку
git checkout -b feature/new-feature

# Делаем изменения, коммитим
git add .
git commit -m "Add new feature"

# Отправляем ветку на GitHub
git push -u origin feature/new-feature
```

### Обновление после изменений

```bash
# Добавляем изменения
git add .

# Коммитим
git commit -m "Описание изменений"

# Отправляем на GitHub
git push
```

### Создание Release на GitHub

1. Перейдите на страницу репозитория
2. Нажмите "Releases" → "Create a new release"
3. Выберите тег `v1.0.0`
4. Заголовок: "Version 1.0.0"
5. Описание: скопируйте из CHANGELOG.md
6. Нажмите "Publish release"

## Полезные команды

```bash
# Просмотр истории коммитов
git log --oneline

# Просмотр изменений
git diff

# Просмотр статуса
git status

# Отмена изменений в файле (до добавления в staging)
git checkout -- filename

# Отмена добавления файла (из staging)
git reset HEAD filename
```

