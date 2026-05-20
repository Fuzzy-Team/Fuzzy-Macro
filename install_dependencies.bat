@echo off
setlocal enabledelayedexpansion

set VENV_NAME=fuzzy-macro-env
set VENV_PATH=%USERPROFILE%\%VENV_NAME%

echo [35mChecking Python installation...[0m

rem Prefer the py launcher to select a supported 3.x version (3.9, 3.8, 3.7)
set "PYTHON_CMD="
where py >nul 2>&1
if %errorlevel%==0 (
    for %%v in (3.9 3.8 3.7) do (
        py -%%v --version >nul 2>&1
        if not errorlevel 1 (
            set "PYTHON_CMD=py -%%v"
            goto :py_found
        )
    )
)
:py_found

rem Fallback to python/python3 on PATH
if not defined PYTHON_CMD (
    where python >nul 2>&1
    if %errorlevel%==0 (
        set "PYTHON_CMD=python"
    ) else (
        where python3 >nul 2>&1
        if %errorlevel%==0 (
            set "PYTHON_CMD=python3"
        )
    )
)

if not defined PYTHON_CMD (
    echo [31mPython 3.7/3.8/3.9 not found on system.[0m
    echo [33mPlease install Python 3.9, 3.8, or 3.7 and ensure it's on PATH or install the py launcher.[0m
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('%PYTHON_CMD% --version 2^>^&1') do set PY_VERSION=%%i
echo [32mFound: %PY_VERSION%[0m

:: Create virtual environment
if not exist "%VENV_PATH%" (
    echo [35mCreating virtual environment at %VENV_PATH% using %PYTHON_CMD%[0m
    %PYTHON_CMD% -m venv "%VENV_PATH%"
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
echo [35mUpgrading pip, pinning setuptools<82, and installing wheel[0m
python -m pip install --upgrade pip "setuptools<82" wheel

:: Install PyTorch first (prefer CUDA on Windows, fallback to default wheels)
echo [35mInstalling PyTorch (GPU if available)[0m
python -m pip install --prefer-binary --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --trusted-host download.pytorch.org --default-timeout=100 --index-url https://download.pytorch.org/whl/cu121 torch torchvision
if %errorlevel% neq 0 (
    echo [33mCUDA PyTorch install failed, falling back to default PyTorch wheels.[0m
    python -m pip install --prefer-binary --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --default-timeout=100 torch torchvision
)

:: Install core packages
echo [35mInstalling libraries[0m
python -m pip install --prefer-binary --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --default-timeout=100 "numpy<2"
python -m pip install --prefer-binary --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --default-timeout=100 "opencv-python-headless<4.11" "numpy<2" --force-reinstall
python -m pip install --prefer-binary --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --default-timeout=100 easyocr
python -m pip install --prefer-binary --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --default-timeout=100 pyautogui
python -m pip install --prefer-binary --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --default-timeout=100 pydirectinput
python -m pip install --prefer-binary --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --default-timeout=100 mss
python -m pip install --prefer-binary --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --default-timeout=100 pillow
python -m pip install --prefer-binary --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --default-timeout=100 discord-webhook
python -m pip install --prefer-binary --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --default-timeout=100 "discord.py"
python -m pip install --prefer-binary --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --default-timeout=100 pypresence
python -m pip install --prefer-binary --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --default-timeout=100 matplotlib
python -m pip install --prefer-binary --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --default-timeout=100 fuzzywuzzy
python -m pip install --prefer-binary --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --default-timeout=100 python-Levenshtein
python -m pip install --prefer-binary --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --default-timeout=100 "pyscreeze<0.1.29"
python -m pip install --prefer-binary --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --default-timeout=100 html2image
python -m pip install --prefer-binary --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --default-timeout=100 gevent
python -m pip install --prefer-binary --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --default-timeout=100 eel
python -m pip install --prefer-binary --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --default-timeout=100 ImageHash
python -m pip install --prefer-binary --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --default-timeout=100 httpx
python -m pip install --prefer-binary --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --default-timeout=100 flask
python -m pip install --prefer-binary --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --default-timeout=100 pygetwindow
python -m pip install --prefer-binary --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --default-timeout=100 requests
python -m pip install --prefer-binary --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --default-timeout=100 "aiohttp==3.10.5"
python -m pip install --prefer-binary --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --default-timeout=100 pynput

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
