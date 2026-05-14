@echo off
chcp 65001 >nul
title TunnelFlow Client

echo ====================================
echo    TunnelFlow - Secure Tunneling
echo ====================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH
    echo Please install Python from https://python.org
    pause
    exit /b 1
)

REM Check if config exists
if not exist "config.json" (
    echo [ERROR] config.json not found!
    echo Please configure your tunnel settings first.
    pause
    exit /b 1
)

:MENU
echo.
echo Select mode:
echo   1. Run once (no auto-reconnect)
echo   2. Run with auto-reconnect (recommended)
echo   3. Configure settings
echo   4. Exit
echo.
set /p choice="Enter choice (1-4): "

if "%choice%"=="1" goto RUN_ONCE
if "%choice%"=="2" goto RUN_AUTO
if "%choice%"=="3" goto CONFIGURE
if "%choice%"=="4" goto EXIT
echo Invalid choice, please try again.
goto MENU

:RUN_ONCE
echo.
echo Starting TunnelFlow in single-connect mode...
python "%~dp0client.py" --once
goto END

:RUN_AUTO
echo.
echo Starting TunnelFlow with auto-reconnect...
echo Press Ctrl+C to stop
echo.
python "%~dp0client.py"
goto END

:CONFIGURE
echo.
echo Current configuration:
if exist "config.json" type "config.json"
echo.
echo Edit config.json to change settings.
pause
goto MENU

:EXIT
exit /b 0

:END
pause
