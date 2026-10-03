@echo off
setlocal EnableExtensions DisableDelayedExpansion
set "PYTHONUTF8=1"

set "PROJECT_ROOT=%~dp0"
set "VENV_PATH=%PROJECT_ROOT%fuzzy-macro-env"
if exist "%VENV_PATH%\Scripts\python.exe" goto :venv_ready
if exist "%USERPROFILE%\fuzzy-macro-env\Scripts\python.exe" set "VENV_PATH=%USERPROFILE%\fuzzy-macro-env"
if exist "%VENV_PATH%\Scripts\python.exe" goto :venv_ready

echo Virtual environment not found. Starting dependency installer...
call "%PROJECT_ROOT%install_dependencies.bat" --no-launch
if errorlevel 1 goto :failed
set "VENV_PATH=%PROJECT_ROOT%fuzzy-macro-env"
if not exist "%VENV_PATH%\Scripts\python.exe" goto :failed

:venv_ready
set "PYTHON_EXE=%VENV_PATH%\Scripts\python.exe"
"%PYTHON_EXE%" -c "import struct, sys; sys.exit(0 if (3, 8) <= sys.version_info[:2] <= (3, 9) and struct.calcsize('P') == 8 else 1)"
if errorlevel 1 (
    echo The virtual environment requires 64-bit Python 3.8 or 3.9.
    echo Run install_dependencies.bat with a supported Python installation.
    goto :failed
)

:: Keep paths out of PowerShell source so apostrophes in folder names work.
powershell -NoProfile -Command "$p = [Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent()); if ($p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { exit 0 } else { exit 1 }" >nul 2>&1
if not errorlevel 1 goto :elevated
set "FUZZY_LAUNCHER=%~f0"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference = 'Stop'; Start-Process -FilePath $env:FUZZY_LAUNCHER -WorkingDirectory $env:PROJECT_ROOT -Verb RunAs"
if errorlevel 1 goto :failed
exit /b 0

:elevated
:: Stop only Fuzzy Macro processes using this venv and main.py.
powershell -NoProfile -ExecutionPolicy Bypass -Command "$pythonPath = [IO.Path]::GetFullPath($env:PYTHON_EXE); Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -and $_.ExecutablePath -ieq $pythonPath -and $_.CommandLine -match '(^|\s)main\.py(\s|$)' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >nul 2>&1
if exist "%VENV_PATH%\Lib\site-packages\certifi\cacert.pem" set "SSL_CERT_FILE=%VENV_PATH%\Lib\site-packages\certifi\cacert.pem"
cd /d "%PROJECT_ROOT%src"
if errorlevel 1 goto :failed
"%PYTHON_EXE%" main.py
set "MACRO_EXIT_CODE=%errorlevel%"
if not "%MACRO_EXIT_CODE%"=="0" pause
exit /b %MACRO_EXIT_CODE%

:failed
echo Fuzzy Macro could not start. See the error above.
pause
exit /b 1
