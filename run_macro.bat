@echo off
setlocal enabledelayedexpansion

:: Ensure script is running as administrator
net session >nul 2>&1
if errorlevel 1 (
    echo Administrator privileges are required. Attempting to elevate...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -WorkingDirectory '%~dp0' -Verb RunAs"
    exit /b
)

:: Kill any running Python processes related to the macro
taskkill /F /IM python.exe >nul 2>&1
taskkill /F /IM python3.exe >nul 2>&1
taskkill /F /IM python3.9.exe >nul 2>&1

set "VENV_NAME=fuzzy-macro-env"
set "PROJECT_ROOT=%~dp0"
set "PROJECT_VENV_PATH=%PROJECT_ROOT%%VENV_NAME%"
set "LEGACY_VENV_PATH=%USERPROFILE%\%VENV_NAME%"
set "VENV_PATH=%PROJECT_VENV_PATH%"

if exist "%PROJECT_VENV_PATH%\Scripts\activate.bat" (
    set "VENV_PATH=%PROJECT_VENV_PATH%"
) else if exist "%LEGACY_VENV_PATH%\Scripts\activate.bat" (
    set "VENV_PATH=%LEGACY_VENV_PATH%"
)

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
    rem Get the virtualenv python version (e.g. 3.9)
    set "VENV_PY_VER="
    for /f "usebackq delims=" %%V in (`python -c "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}')" 2^>nul`) do set "VENV_PY_VER=%%V"
    echo Virtualenv python: %VENV_PY_VER%

    rem If venv Python is 3.7/3.8/3.9, use it. Otherwise search for a suitable system Python.
    set "PY_EXEC="
    if "%VENV_PY_VER%"=="3.9" set "PY_EXEC=python"
    if "%VENV_PY_VER%"=="3.8" set "PY_EXEC=python"
    if "%VENV_PY_VER%"=="3.7" set "PY_EXEC=python"

    if defined PY_EXEC (
        echo Using virtualenv Python %VENV_PY_VER%
        python main.py
        if errorlevel 1 pause
    ) else (
        echo Virtualenv Python is not 3.7/3.8/3.9 - searching system interpreters...

        rem Prefer the py launcher if available
        where py >nul 2>&1
        if %errorlevel%==0 (
            for %%v in (3.9 3.8 3.7) do (
                py -%%v -c "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}')" >nul 2>&1
                if not errorlevel 1 (
                    set "PY_EXEC=py -%%v"
                    goto :found_python
                )
            )
        )

        rem Try explicit executables on PATH
        for %%e in (python3.9.exe python3.8.exe python3.7.exe python3.exe python.exe) do (
            for /f "usebackq delims=" %%W in (`"%%~e" -c "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}')" 2^>nul`) do (
                if "%%W"=="3.9" set "PY_EXEC=%%~e" & goto :found_python
                if "%%W"=="3.8" set "PY_EXEC=%%~e" & goto :found_python
                if "%%W"=="3.7" set "PY_EXEC=%%~e" & goto :found_python
            )
        )

:found_python
        if defined PY_EXEC (
            echo Found Python: %PY_EXEC%
            %PY_EXEC% main.py
            if errorlevel 1 pause
        ) else (
            echo No Python 3.7, 3.8, or 3.9 found on PATH or via the py launcher.
            echo Please install one of these versions or ensure it's on PATH, then rerun.
            pause
        )
    )
) else (
    echo Virtual environment not found at %VENV_PATH%
    echo Starting dependency installer...
    cd /d "%~dp0"
    call "%~dp0install_dependencies.bat"
)
