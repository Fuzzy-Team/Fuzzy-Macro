@echo off
setlocal EnableExtensions DisableDelayedExpansion
set "PYTHONUTF8=1"

set "PROJECT_ROOT=%~dp0"
set "VENV_PATH=%PROJECT_ROOT%fuzzy-macro-env"
if exist "%VENV_PATH%\Scripts\python.exe" goto :venv_ready
if exist "%USERPROFILE%\fuzzy-macro-env\Scripts\python.exe" set "VENV_PATH=%USERPROFILE%\fuzzy-macro-env"
if exist "%VENV_PATH%\Scripts\python.exe" goto :venv_ready

:: The bundled bitmap matcher and Windows dependencies require x64 Python 3.8/3.9.
echo Checking Python installation...
set "PYTHON_CMD="
call :try_python py -3.9
if not defined PYTHON_CMD call :try_python py -3.8
if not defined PYTHON_CMD call :try_python python3.9.exe
if not defined PYTHON_CMD call :try_python python3.8.exe
if not defined PYTHON_CMD call :try_python python.exe
if not defined PYTHON_CMD call :try_python python3.exe
if not defined PYTHON_CMD (
    echo Install 64-bit Python 3.9 or 3.8 with the Python launcher or add it to PATH.
    goto :failed
)

echo Creating virtual environment at "%VENV_PATH%"...
%PYTHON_CMD% -m venv "%VENV_PATH%"
if errorlevel 1 goto :failed

:venv_ready
set "PYTHON_EXE=%VENV_PATH%\Scripts\python.exe"
"%PYTHON_EXE%" -c "import struct, sys; sys.exit(0 if (3, 8) <= sys.version_info[:2] <= (3, 9) and struct.calcsize('P') == 8 else 1)"
if errorlevel 1 (
    echo Existing virtual environment requires 64-bit Python 3.8 or 3.9.
    echo Rename "%VENV_PATH%" and run this installer again to create a supported environment.
    goto :failed
)
cd /d "%PROJECT_ROOT%"
if errorlevel 1 goto :failed

"%PYTHON_EXE%" -m pip install --upgrade pip "setuptools<82" wheel
if errorlevel 1 goto :failed

:: Remove conflicting cv2 distributions before installing one pinned version.
"%PYTHON_EXE%" -m pip uninstall -y opencv-python opencv-contrib-python opencv-python-headless opencv-contrib-python-headless
if errorlevel 1 goto :failed
"%PYTHON_EXE%" -m pip install --prefer-binary --default-timeout=100 -r "%PROJECT_ROOT%requirements-windows.txt"
if errorlevel 1 goto :failed
"%PYTHON_EXE%" -m pip check
if errorlevel 1 goto :failed
"%PYTHON_EXE%" -c "import cv2, easyocr, eel, pydirectinput, sys; sys.path.insert(0, 'src'); from modules import bitmap_matcher; assert bitmap_matcher._bitmap_matcher; assert callable(bitmap_matcher.find_bitmap_cython); assert callable(bitmap_matcher.find_all_bitmap_cython)"
if errorlevel 1 goto :failed

echo Installation complete.
if /i "%~1"=="--no-launch" exit /b 0
call "%PROJECT_ROOT%run_macro.bat"
exit /b %errorlevel%

:try_python
if defined PYTHON_CMD exit /b 0
%* -c "import struct, sys; sys.exit(0 if (3, 8) <= sys.version_info[:2] <= (3, 9) and struct.calcsize('P') == 8 else 1)" >nul 2>&1
if not errorlevel 1 set "PYTHON_CMD=%*"
exit /b 0

:failed
echo Dependency installation failed. See the error above.
pause
exit /b 1
