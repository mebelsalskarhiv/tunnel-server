# Быстрый старт

## Для отправки на GitHub

### 1. Создайте репозиторий на GitHub

Перейдите на https://github.com/new и создайте новый репозиторий:
- **Название**: `tunnel-server` (или другое)
- **Описание**: "Tunnel server for exposing local services to the internet"
- **НЕ добавляйте** README, .gitignore или license (они уже есть)

### 2. Подключите репозиторий

```bash
# Замените YOUR_USERNAME на ваш GitHub username
git remote add origin https://github.com/YOUR_USERNAME/tunnel-server.git
```

### 3. Отправьте код

```bash
# Отправляем на GitHub
git push -u origin main

# Если ваша ветка называется master:
# git push -u origin master
```

### 4. Создайте тег версии (опционально)

```bash
git tag -a v1.0.0 -m "Version 1.0.0 - Initial release"
git push origin v1.0.0
```

## Если нужна авторизация

GitHub больше не принимает пароли. Используйте:

### Personal Access Token (HTTPS)

1. Перейдите: https://github.com/settings/tokens
2. Создайте новый token с правами `repo`
3. Используйте token вместо пароля при `git push`

### SSH ключ (рекомендуется)

1. Создайте SSH ключ (если нет):
   ```bash
   ssh-keygen -t ed25519 -C "your_email@example.com"
   ```

2. Добавьте ключ в GitHub:
   - Скопируйте содержимое `~/.ssh/id_ed25519.pub`
   - Перейдите: https://github.com/settings/keys
   - Нажмите "New SSH key" и вставьте ключ

3. Используйте SSH URL:
   ```bash
   git remote set-url origin git@github.com:YOUR_USERNAME/tunnel-server.git
   ```

## Проверка

После отправки проверьте:
- ✅ Код загружен на GitHub
- ✅ README.md отображается
- ✅ Все файлы на месте

