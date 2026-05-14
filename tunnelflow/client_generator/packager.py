"""
TunnelFlow Client Package Generator
Creates ready-to-use client packages with configuration
"""

import os
import json
import zipfile
import shutil
from pathlib import Path
from typing import Optional
from datetime import datetime


# Шаблоны скриптов
WINDOWS_BATCH_TEMPLATE = """@echo off
chcp 65001 >nul
echo ============================================
echo   TunnelFlow Client Launcher
echo ============================================
echo.
echo Tunnel: {tunnel_name}
echo Server: {server}
echo Local Port: {local_port}
echo.
echo Choose launch mode:
echo   1. Run once (manual)
echo   2. Install as Windows Service (auto-start)
echo   3. Uninstall service
echo   4. Exit
echo.
set /p choice="Your choice (1-4): "

if "%choice%"=="1" goto RUN_ONCE
if "%choice%"=="2" goto INSTALL_SERVICE
if "%choice%"=="3" goto UNINSTALL_SERVICE
if "%choice%"=="4" goto EXIT

echo Invalid choice!
goto EXIT

:RUN_ONCE
echo.
echo Starting tunnel client...
tunnel_client.exe --config config.json
pause
goto EXIT

:INSTALL_SERVICE
echo.
echo Installing TunnelFlow as Windows Service...
sc create TunnelFlow binPath= "{full_path}\\tunnel_client.exe --config config.json" start= auto
sc description TunnelFlow "TunnelFlow - Secure tunnel to {subdomain}.{base_domain}"
net start TunnelFlow
echo Service installed and started!
echo The tunnel will start automatically on Windows boot.
pause
goto EXIT

:UNINSTALL_SERVICE
echo.
echo Uninstalling TunnelFlow service...
net stop TunnelFlow 2>nul
sc delete TunnelFlow
echo Service uninstalled!
pause
goto EXIT

:EXIT
echo.
echo Goodbye!
"""

LINUX_SCRIPT_TEMPLATE = """#!/bin/bash

echo "============================================"
echo "  TunnelFlow Client Launcher"
echo "============================================"
echo ""
echo "Tunnel: {tunnel_name}"
echo "Server: {server}"
echo "Local Port: {local_port}"
echo ""
echo "Choose launch mode:"
echo "  1. Run once (manual)"
echo "  2. Install as systemd service (auto-start)"
echo "  3. Uninstall service"
echo "  4. Exit"
echo ""
read -p "Your choice (1-4): " choice

case $choice in
    1)
        echo ""
        echo "Starting tunnel client..."
        ./tunnel_client --config config.json
        ;;
    2)
        echo ""
        echo "Installing systemd service..."
        sudo tee /etc/systemd/system/tunnelflow.service > /dev/null <<EOF
[Unit]
Description=TunnelFlow Client - {tunnel_name}
After=network.target

[Service]
Type=simple
User={username}
WorkingDirectory={full_path}
ExecStart={full_path}/tunnel_client --config config.json
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
        sudo systemctl daemon-reload
        sudo systemctl enable tunnelflow
        sudo systemctl start tunnelflow
        echo "Service installed and started!"
        echo "The tunnel will start automatically on boot."
        ;;
    3)
        echo ""
        echo "Uninstalling service..."
        sudo systemctl stop tunnelflow
        sudo systemctl disable tunnelflow
        sudo rm /etc/systemd/system/tunnelflow.service
        sudo systemctl daemon-reload
        echo "Service uninstalled!"
        ;;
    4)
        echo ""
        echo "Goodbye!"
        exit 0
        ;;
    *)
        echo "Invalid choice!"
        exit 1
        ;;
esac
"""

MACOS_SCRIPT_TEMPLATE = """#!/bin/bash

echo "============================================"
echo "  TunnelFlow Client Launcher"
echo "============================================"
echo ""
echo "Tunnel: {tunnel_name}"
echo "Server: {server}"
echo "Local Port: {local_port}"
echo ""
echo "Choose launch mode:"
echo "  1. Run once (manual)"
echo "  2. Install as LaunchAgent (auto-start)"
echo "  3. Uninstall LaunchAgent"
echo "  4. Exit"
echo ""
read -p "Your choice (1-4): " choice

case $choice in
    1)
        echo ""
        echo "Starting tunnel client..."
        ./tunnel_client --config config.json
        ;;
    2)
        echo ""
        echo "Installing LaunchAgent..."
        mkdir -p ~/Library/LaunchAgents
        cat > ~/Library/LaunchAgents/com.tunnelflow.client.plist <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.tunnelflow.client</string>
    <key>ProgramArguments</key>
    <array>
        <string>{full_path}/tunnel_client</string>
        <string>--config</string>
        <string>{full_path}/config.json</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>{full_path}/tunnelflow.log</string>
    <key>StandardErrorPath</key>
    <string>{full_path}/tunnelflow.err</string>
</dict>
</plist>
EOF
        launchctl load ~/Library/LaunchAgents/com.tunnelflow.client.plist
        echo "LaunchAgent installed and started!"
        echo "The tunnel will start automatically on login."
        ;;
    3)
        echo ""
        echo "Uninstalling LaunchAgent..."
        launchctl unload ~/Library/LaunchAgents/com.tunnelflow.client.plist 2>/dev/null
        rm ~/Library/LaunchAgents/com.tunnelflow.client.plist
        echo "LaunchAgent uninstalled!"
        ;;
    4)
        echo ""
        echo "Goodbye!"
        exit 0
        ;;
    *)
        echo "Invalid choice!"
        exit 1
        ;;
esac
"""

CONFIG_TEMPLATE = """{{
  "tunnel_id": {tunnel_id},
  "tunnel_name": "{tunnel_name}",
  "token": "{token}",
  "server": "{server}",
  "port": 443,
  "local_port": {local_port},
  "subdomain": "{subdomain}",
  "base_domain": "{base_domain}",
  "ssl_enabled": true,
  "auto_reconnect": true,
  "reconnect_delay_seconds": 5,
  "max_reconnect_delay_seconds": 60,
  "heartbeat_interval_seconds": 30,
  "log_level": "info",
  "log_file": "client.log"
}}
"""

README_TEMPLATE = """# TunnelFlow Client Package

## Что внутри?

- `tunnel_client` / `tunnel_client.exe` - клиентское приложение
- `config.json` - конфигурация вашего туннеля
- `run.bat` (Windows) / `run.sh` (Linux/Mac) - скрипт запуска
- Этот файл с инструкцией

## Быстрый старт

### Windows
1. Запустите `run.bat`
2. Выберите режим запуска (1 - разово, 2 - автозапуск)
3. Готово! Туннель активен

### Linux
```bash
chmod +x run.sh
./run.sh
```

### macOS
```bash
chmod +x run.sh
./run.sh
```

## Режимы работы

### Разовый запуск
Клиент запускается в текущем окне терминала. 
При закрытии окна туннель отключается.

### Автозапуск (служба)
Клиент устанавливается как системная служба:
- **Windows**: Служба Windows
- **Linux**: systemd service
- **macOS**: LaunchAgent

Служба запускается автоматически при загрузке системы.

## Конфигурация

Файл `config.json` содержит все настройки:
- ID туннеля и токен доступа
- Адрес сервера
- Локальный порт для проброса
- Настройки SSL и авто-переподключения

**Не передавайте этот файл третьим лицам!**

## Логи

Логи сохраняются в файл `client.log` в текущей директории.

## Поддержка

Если возникли проблемы:
1. Проверьте подключение к интернету
2. Убедитесь, что локальный порт доступен
3. Посмотрите логи в `client.log`
4. Обратитесь в поддержку: support@tunnelflow.io

## URL вашего туннеля

HTTPS: https://{subdomain}.{base_domain}

---
Generated: {generated_at}
TunnelFlow v2.0
"""


class ClientPackageGenerator:
    """Генератор клиентских пакетов"""
    
    def __init__(self, base_domain: str = "tunnelflow.io", server_host: str = "tunnel.tunnelflow.io"):
        self.base_domain = base_domain
        self.server_host = server_host
        self.template_dir = Path(__file__).parent / "templates"
    
    def generate_package(
        self,
        tunnel_id: int,
        tunnel_name: str,
        token: str,
        local_port: int,
        subdomain: str,
        output_dir: str,
        platform: str = "all",  # all, windows, linux, macos
        include_client_binary: bool = False,
    ) -> str:
        """
        Сгенерировать клиентский пакет
        
        Args:
            tunnel_id: ID туннеля
            tunnel_name: Название туннеля
            token: Токен доступа
            local_port: Локальный порт
            subdomain: Поддомен
            output_dir: Директория для сохранения
            platform: Целевая платформа
            include_client_binary: Включить ли бинарник клиента
        
        Returns:
            Путь к ZIP архиву
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Создаем временную директорию для сборки
        temp_dir = output_path / f"tunnelflow_{subdomain}"
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        temp_dir.mkdir()
        
        generated_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        
        # Генерируем config.json
        config_content = CONFIG_TEMPLATE.format(
            tunnel_id=tunnel_id,
            tunnel_name=tunnel_name.replace('"', '\\"'),
            token=token,
            server=self.server_host,
            local_port=local_port,
            subdomain=subdomain,
            base_domain=self.base_domain,
        )
        (temp_dir / "config.json").write_text(config_content)
        
        # Генерируем README
        readme_content = README_TEMPLATE.format(
            subdomain=subdomain,
            base_domain=self.base_domain,
            generated_at=generated_at,
        )
        (temp_dir / "README.txt").write_text(readme_content)
        
        # Генерируем скрипты для нужных платформ
        if platform in ["all", "windows"]:
            batch_content = WINDOWS_BATCH_TEMPLATE.format(
                tunnel_name=tunnel_name,
                server=self.server_host,
                local_port=local_port,
                subdomain=subdomain,
                base_domain=self.base_domain,
                full_path="%~dp0",  # Batch script directory
            )
            (temp_dir / "run.bat").write_text(batch_content)
        
        if platform in ["all", "linux"]:
            linux_content = LINUX_SCRIPT_TEMPLATE.format(
                tunnel_name=tunnel_name,
                server=self.server_host,
                local_port=local_port,
                username="$USER",
                full_path="$(cd \"$(dirname \"$0\")\" && pwd)",
            )
            linux_script = temp_dir / "run.sh"
            linux_script.write_text(linux_content)
            os.chmod(linux_script, 0o755)
        
        if platform in ["all", "macos"]:
            macos_content = MACOS_SCRIPT_TEMPLATE.format(
                tunnel_name=tunnel_name,
                server=self.server_host,
                local_port=local_port,
                full_path="$(cd \"$(dirname \"$0\")\" && pwd)",
            )
            macos_script = temp_dir / "run.sh"
            if not macos_script.exists():
                macos_script.write_text(macos_content)
                os.chmod(macos_script, 0o755)
        
        # Копируем бинарник клиента если нужно
        if include_client_binary:
            # Здесь должна быть логика копирования предкомпиллированных бинарников
            # Для примера создаем заглушку
            if platform in ["all", "windows"]:
                (temp_dir / "tunnel_client.exe").write_text("BINARY_PLACEHOLDER")
            if platform in ["all", "linux"]:
                binary = temp_dir / "tunnel_client"
                binary.write_text("BINARY_PLACEHOLDER")
                os.chmod(binary, 0o755)
            if platform in ["all", "macos"]:
                binary = temp_dir / "tunnel_client_macos"
                binary.write_text("BINARY_PLACEHOLDER")
                os.chmod(binary, 0o755)
        
        # Создаем ZIP архив
        zip_filename = f"tunnelflow_{subdomain}_{platform}.zip"
        zip_path = output_path / zip_filename
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in temp_dir.rglob("*"):
                if file_path.is_file():
                    arcname = file_path.relative_to(output_path)
                    zipf.write(file_path, arcname)
        
        # Очищаем временную директорию
        shutil.rmtree(temp_dir)
        
        return str(zip_path)
    
    def generate_config_only(
        self,
        tunnel_id: int,
        tunnel_name: str,
        token: str,
        local_port: int,
        subdomain: str,
        output_path: str,
    ) -> str:
        """Сгенерировать только config.json"""
        config_content = CONFIG_TEMPLATE.format(
            tunnel_id=tunnel_id,
            tunnel_name=tunnel_name.replace('"', '\\"'),
            token=token,
            server=self.server_host,
            local_port=local_port,
            subdomain=subdomain,
            base_domain=self.base_domain,
        )
        
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(config_content)
        
        return str(path)
