@echo off
setlocal EnableExtensions DisableDelayedExpansion
set "PYTHONUTF8=1"

set "PROJECT_ROOT=%~dp0"
set "VENV_PATH=%USERPROFILE%\fuzzy-macro-env"
set "PYTHON_EXE=%VENV_PATH%\Scripts\python.exe"

if not exist "%PYTHON_EXE%" (
    echo Virtual environment not found. Installing dependencies first...
    call "%PROJECT_ROOT%install_dependencies.bat" --no-launch
    if errorlevel 1 exit /b 1
)

:: Screen reading and game input need administrator rights, so relaunch elevated. The path goes through an
:: environment variable so apostrophes in folder names work.
fltmc >nul 2>&1
if not errorlevel 1 goto :elevated
set "FUZZY_LAUNCHER=%~f0"
powershell -NoProfile -Command "Start-Process -FilePath $env:FUZZY_LAUNCHER -WorkingDirectory $env:PROJECT_ROOT -Verb RunAs" >nul 2>&1
if errorlevel 1 (
    echo Fuzzy Macro needs administrator access. Run this again and choose Yes at the prompt.
    pause
    exit /b 1
)
exit /b 0

:elevated
:: Let dependency updates finish before stopping the old process tree.
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -ieq 'cmd.exe' -and $_.CommandLine -like '*install_dependencies.bat*' -and $_.CommandLine -match '--no-launch(?:\s|$)' } | ForEach-Object { Write-Host 'Waiting for dependency installation to finish...'; Wait-Process -Id $_.ProcessId -ErrorAction SilentlyContinue }"

:: Stop only a Fuzzy Macro already running from this virtual environment, with its macro, bot and manager processes (/T).
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -ieq $env:PYTHON_EXE -and $_.CommandLine -match 'main\.py' } | ForEach-Object { taskkill /PID $_.ProcessId /T /F }" >nul 2>&1

:: Force Python to use certifi for SSL (fixes Discord/aiohttp)
if exist "%VENV_PATH%\Lib\site-packages\certifi\cacert.pem" set "SSL_CERT_FILE=%VENV_PATH%\Lib\site-packages\certifi\cacert.pem"

cd /d "%PROJECT_ROOT%src"
"%PYTHON_EXE%" main.py
if errorlevel 1 pause
