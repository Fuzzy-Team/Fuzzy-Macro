@echo off
setlocal enabledelayedexpansion

:: Kill any running Python processes related to the macro
taskkill /F /IM python.exe >nul 2>&1
taskkill /F /IM python3.exe >nul 2>&1
taskkill /F /IM python3.9.exe >nul 2>&1

set VENV_NAME=fuzzy-macro-env
set VENV_PATH=%USERPROFILE%\%VENV_NAME%

:: Set SSL certificate file for aiohttp/discord compatibility
if exist "%VENV_PATH%\Lib\site-packages\certifi\cacert.pem" (
    set SSL_CERT_FILE=%VENV_PATH%\Lib\site-packages\certifi\cacert.pem
)

:: Change to the directory where this batch file is located
cd /d "%~dp0"
cd src

if exist "%VENV_PATH%\Scripts\activate.bat" (
    echo Activating virtual environment...
    call "%VENV_PATH%\Scripts\activate.bat"
    echo.
    python --version
    python main.py
) else (
    echo Virtual environment not found at %VENV_PATH%
    echo Please run install_dependencies.bat first.
    pause
)
