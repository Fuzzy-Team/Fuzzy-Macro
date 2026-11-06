@echo off
setlocal EnableExtensions DisableDelayedExpansion
set "PYTHONUTF8=1"

:: The venv lives outside the macro folder, like on macOS, so updates never touch it.
set "PROJECT_ROOT=%~dp0"
set "VENV_PATH=%USERPROFILE%\fuzzy-macro-env"
set "PYTHON_EXE=%VENV_PATH%\Scripts\python.exe"
set "VERSION_CHECK=import struct, sys; sys.exit(0 if (3, 8) <= sys.version_info[:2] <= (3, 9) and struct.calcsize('P') == 8 else 1)"

if exist "%PYTHON_EXE%" goto :venv_ready

:: The bundled bitmap matcher is built for 64-bit Python 3.8 and 3.9.
set "PYTHON_CMD="
call :try_python py -3.9
if not defined PYTHON_CMD call :try_python py -3.8
if not defined PYTHON_CMD call :try_python python
if not defined PYTHON_CMD (
    echo Install 64-bit Python 3.9 or 3.8 from python.org, then run this again.
    goto :failed
)
echo Creating virtual environment at "%VENV_PATH%"
%PYTHON_CMD% -m venv "%VENV_PATH%"
if errorlevel 1 goto :failed

:venv_ready
"%PYTHON_EXE%" -c "%VERSION_CHECK%"
if errorlevel 1 (
    echo The virtual environment at "%VENV_PATH%" is not 64-bit Python 3.8 or 3.9.
    echo Rename or delete that folder and run this again.
    goto :failed
)

"%PYTHON_EXE%" -m pip install --upgrade pip "setuptools<82" wheel
if errorlevel 1 goto :failed
:: Every OpenCV package shares the cv2 module, so keep only the one in requirements-windows.txt.
"%PYTHON_EXE%" -m pip uninstall -y opencv-python opencv-contrib-python opencv-python-headless opencv-contrib-python-headless
"%PYTHON_EXE%" -m pip install --prefer-binary --default-timeout=100 -r "%PROJECT_ROOT%requirements-windows.txt"
if errorlevel 1 goto :failed

echo Installation complete.
if /i "%~1"=="--no-launch" exit /b 0
call "%PROJECT_ROOT%run_macro.bat"
exit /b %errorlevel%

:try_python
if defined PYTHON_CMD exit /b 0
%* -c "%VERSION_CHECK%" >nul 2>&1
if not errorlevel 1 set "PYTHON_CMD=%*"
exit /b 0

:failed
echo Dependency installation failed. See the error above.
pause
exit /b 1
