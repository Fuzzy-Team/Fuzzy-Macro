@echo off
setlocal enabledelayedexpansion

set VENV_NAME=fuzzy-macro-env
set VENV_PATH=%USERPROFILE%\%VENV_NAME%
set PYTHON_VER=3.9

echo [35mChecking Python installation...[0m

where python >nul 2>&1
if %errorlevel% neq 0 (
    where python3 >nul 2>&1
    if %errorlevel% neq 0 (
        echo [31mPython is not installed or not in PATH.[0m
        echo [33mPlease download and install Python 3.9 from https://www.python.org/downloads/[0m
        echo [33mMake sure to check "Add Python to PATH" during installation.[0m
        pause
        exit /b 1
    ) else (
        set PYTHON_CMD=python3
    )
) else (
    set PYTHON_CMD=python
)

for /f "tokens=*" %%i in ('!PYTHON_CMD! --version 2^>^&1') do set PY_VERSION=%%i
echo [32mFound: !PY_VERSION![0m

:: Create virtual environment
if not exist "%VENV_PATH%" (
    echo [35mCreating virtual environment at %VENV_PATH%[0m
    !PYTHON_CMD! -m venv "%VENV_PATH%"
    if %errorlevel% neq 0 (
        echo [31mFailed to create virtual environment.[0m
        pause
        exit /b 1
    )
) else (
    echo [32mVirtual environment already exists at %VENV_PATH%[0m
)

:: Activate virtual environment
echo [35mActivating virtual environment[0m
call "%VENV_PATH%\Scripts\activate.bat"
if %errorlevel% neq 0 (
    echo [31mFailed to activate virtual environment.[0m
    pause
    exit /b 1
)

:: Upgrade pip
echo [35mUpgrading pip, setuptools, and wheel[0m
python -m pip install --upgrade pip setuptools wheel

:: Install PyTorch first (prefer CUDA on Windows, fallback to default wheels)
echo [35mInstalling PyTorch (GPU if available)[0m
pip install --prefer-binary --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --trusted-host download.pytorch.org --default-timeout=100 --index-url https://download.pytorch.org/whl/cu121 torch torchvision torchaudio
if %errorlevel% neq 0 (
    echo [33mCUDA PyTorch install failed, falling back to default PyTorch wheels.[0m
    pip install --prefer-binary --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --default-timeout=100 torch torchvision torchaudio
)

:: Install core packages
echo [35mInstalling libraries[0m
pip install --prefer-binary --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --default-timeout=100 "numpy<2"
pip install --prefer-binary --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --default-timeout=100 "opencv-python-headless<4.11" "numpy<2" --force-reinstall
pip install --prefer-binary --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --default-timeout=100 easyocr
pip install --prefer-binary --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --default-timeout=100 pyautogui
pip install --prefer-binary --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --default-timeout=100 mss
pip install --prefer-binary --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --default-timeout=100 pillow
pip install --prefer-binary --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --default-timeout=100 discord-webhook
pip install --prefer-binary --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --default-timeout=100 "discord.py"
pip install --prefer-binary --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --default-timeout=100 pypresence
pip install --prefer-binary --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --default-timeout=100 matplotlib
pip install --prefer-binary --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --default-timeout=100 fuzzywuzzy
pip install --prefer-binary --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --default-timeout=100 python-Levenshtein
pip install --prefer-binary --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --default-timeout=100 "pyscreeze<0.1.29"
pip install --prefer-binary --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --default-timeout=100 html2image
pip install --prefer-binary --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --default-timeout=100 gevent
pip install --prefer-binary --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --default-timeout=100 eel
pip install --prefer-binary --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --default-timeout=100 ImageHash
pip install --prefer-binary --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --default-timeout=100 httpx
pip install --prefer-binary --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --default-timeout=100 flask
pip install --prefer-binary --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --default-timeout=100 pygetwindow
pip install --prefer-binary --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --default-timeout=100 requests
pip install --prefer-binary --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --default-timeout=100 "aiohttp==3.10.5"
pip install --prefer-binary --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --default-timeout=100 pynput

:: Install certifi and update SSL certificates
python -c "import subprocess, sys; subprocess.check_call([sys.executable, '-E', '-s', '-m', 'pip', 'install', '--upgrade', 'certifi'])"

:: Fix html2image chrome_cdp.py for Python 3.7 compatibility
python -c ^
"import os, importlib.util; spec = importlib.util.find_spec('html2image'); ^
path = os.path.join(os.path.dirname(spec.origin), 'browsers', 'chrome_cdp.py') if spec and spec.origin else None; ^
linesToRemove = [\"print(f'{r.json()=}')\", \"print(f'cdp_send: {method=} {params=}')\", \"print(f'{method=}')\", \"print(f'{message=}')\"] if path and os.path.exists(path) else []; ^
[open(path, 'w').write(open(path).read().replace(l, '')) for l in linesToRemove] if linesToRemove else None"

echo.
echo.
echo [32mInstallation complete![0m
pause
