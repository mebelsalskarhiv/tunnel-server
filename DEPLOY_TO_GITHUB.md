# Инструкция по отправке на GitHub

## Шаг 1: Настройка Git (если еще не настроено)

```bash
# Настройте ваше имя и email (замените на свои данные)
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"

# Или только для этого репозитория:
git config user.name "Your Name"
git config user.email "your.email@example.com"
```

## Шаг 2: Создание коммита

```bash
# Коммит уже создан, но если нужно пересоздать:
git commit -m "Initial commit: Tunnel Server v1.0.0"
```

## Шаг 3: Создание репозитория на GitHub

1. Перейдите на https://github.com/new
2. Заполните:
   - **Repository name**: `tunnel-server`
   - **Description**: "Tunnel server for exposing local services to the internet"
   - **Visibility**: Private или Public
   - **НЕ добавляйте** README, .gitignore или license (они уже есть)
3. Нажмите "Create repository"

## Шаг 4: Подключение к GitHub

```bash
# Замените mebelsalskarhiv на ваш GitHub username
git remote add origin https://github.com/mebelsalskarhiv/tunnel-server.git

# Проверьте подключение
git remote -v
```

## Шаг 5: Отправка на GitHub

### Вариант A: HTTPS (требует Personal Access Token)

```bash
# Отправляем код
git push -u origin master

# Если GitHub попросит авторизацию:
# - Username: ваш GitHub username
# - Password: используйте Personal Access Token (НЕ пароль!)
```

**Как получить Personal Access Token:**
1. Перейдите: https://github.com/settings/tokens
2. Нажмите "Generate new token (classic)"
3. Выберите права: `repo` (полный доступ к репозиториям)
4. Скопируйте токен и используйте его как пароль

### Вариант B: SSH (рекомендуется)

```bash
# Измените URL на SSH
git remote set-url origin git@github.com:mebelsalskarhiv/tunnel-server.git

# Отправляем код
git push -u origin master
```

**Настройка SSH ключа (если еще нет):**
```bash
# Создайте SSH ключ
ssh-keygen -t ed25519 -C "your_email@example.com"

# Скопируйте публичный ключ
cat ~/.ssh/id_ed25519.pub

# Добавьте ключ в GitHub:
# 1. Перейдите: https://github.com/settings/keys
# 2. Нажмите "New SSH key"
# 3. Вставьте содержимое id_ed25519.pub
```

## Шаг 6: Создание тега версии (опционально)

```bash
# Создаем тег
git tag -a v1.0.0 -m "Version 1.0.0 - Initial release"

# Отправляем тег
git push origin v1.0.0
```

## Шаг 7: Создание Release на GitHub

1. Перейдите на страницу репозитория
2. Нажмите "Releases" → "Create a new release"
3. Выберите тег `v1.0.0`
4. Заголовок: "Version 1.0.0"
5. Описание: скопируйте из CHANGELOG.md
6. Нажмите "Publish release"

## Проверка

После выполнения всех шагов:
- ✅ Код должен быть на GitHub
- ✅ README.md должен отображаться
- ✅ Все файлы должны быть на месте

## Полезные команды

```bash
# Проверка статуса
git status

# Просмотр истории
git log --oneline

# Просмотр удаленных репозиториев
git remote -v

# Изменение URL удаленного репозитория
git remote set-url origin <new-url>
```

## Если что-то пошло не так

### Отмена последнего коммита (но сохранить изменения)
```bash
git reset --soft HEAD~1
```

### Удаление remote
```bash
git remote remove origin
```

### Проверка конфигурации Git
```bash
git config --list
```

