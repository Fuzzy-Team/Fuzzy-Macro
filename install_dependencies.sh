#!/usr/bin/env bash
set -euo pipefail

VENV_NAME="fuzzy-macro-env"
PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
PROJECT_VENV_PATH="$PROJECT_ROOT/$VENV_NAME"
LEGACY_VENV_PATH="$HOME/$VENV_NAME"
VENV_PATH="$PROJECT_VENV_PATH"

if [ -x "$PROJECT_VENV_PATH/bin/python" ]; then
    VENV_PATH="$PROJECT_VENV_PATH"
elif [ -x "$LEGACY_VENV_PATH/bin/python" ]; then
    VENV_PATH="$LEGACY_VENV_PATH"
fi

printf "\033[1;35mChecking Python installation...\033[0m\n"

PYTHON_CMD=""
for candidate in python3.9 python3.8 python3.7 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
        ver="$("$candidate" -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")' 2>/dev/null || true)"
        case "$ver" in
            3.9|3.8|3.7)
                PYTHON_CMD="$candidate"
                break
                ;;
        esac
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    printf "\033[31mPython 3.7/3.8/3.9 not found on system.\033[0m\n"
    printf "\033[33mInstall Python 3.9 (recommended), then rerun this script.\033[0m\n"
    exit 1
fi

printf "\033[32mFound: %s (%s)\033[0m\n" "$("$PYTHON_CMD" --version 2>&1)" "$PYTHON_CMD"

if [ ! -d "$VENV_PATH" ]; then
    printf "\033[1;35mCreating virtual environment at %s\033[0m\n" "$VENV_PATH"
    "$PYTHON_CMD" -m venv "$VENV_PATH"
else
    printf "\033[32mVirtual environment already exists at %s\033[0m\n" "$VENV_PATH"
fi

printf "\033[1;35mActivating virtual environment\033[0m\n"
# shellcheck disable=SC1090
source "$VENV_PATH/bin/activate"

printf "\033[1;35mUpgrading pip, pinning setuptools<82, and installing wheel\033[0m\n"
python -m pip install --upgrade pip "setuptools<82" wheel

printf "\033[1;35mInstalling PyTorch (CPU wheels)\033[0m\n"
if ! python -m pip install --prefer-binary --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --trusted-host download.pytorch.org --default-timeout=100 --index-url https://download.pytorch.org/whl/cpu torch torchvision; then
    printf "\033[33mCPU PyTorch index failed, falling back to default PyTorch wheels.\033[0m\n"
    python -m pip install --prefer-binary --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --default-timeout=100 torch torchvision
fi

printf "\033[1;35mInstalling libraries\033[0m\n"
python -m pip install --prefer-binary --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --default-timeout=100 "numpy<2"
python -m pip install --prefer-binary --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --default-timeout=100 "opencv-python-headless<4.11" "numpy<2" --force-reinstall
python -m pip install --prefer-binary --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --default-timeout=100 easyocr
python -m pip install --prefer-binary --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --default-timeout=100 pyautogui
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
python -m pip install --prefer-binary --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --default-timeout=100 "cython" "numpy<2"

python -c "import subprocess, sys; subprocess.check_call([sys.executable, '-E', '-s', '-m', 'pip', 'install', '--upgrade', 'certifi'])"

printf "\033[1;35mBuilding native bitmap_matcher for this Python...\033[0m\n"
if ! python "$PROJECT_ROOT/src/modules/bitmap_matcher/build_native.py"; then
  printf "\033[33mNative bitmap_matcher build failed. Ensure a C compiler is installed (build-essential / gcc) and rerun.\033[0m\n"
  printf "\033[33mThe macro will also attempt to build it automatically on startup.\033[0m\n"
fi

# Fix html2image chrome_cdp.py for older Python compatibility
python - <<'PY'
import os, importlib.util
spec = importlib.util.find_spec('html2image')
path = os.path.join(os.path.dirname(spec.origin), 'browsers', 'chrome_cdp.py') if spec and spec.origin else None
lines_to_remove = [
    "print(f'{r.json()=}')",
    "print(f'cdp_send: {method=} {params=}')",
    "print(f'{method=}')",
    "print(f'{message=}')",
]
if path and os.path.exists(path):
    text = open(path).read()
    for line in lines_to_remove:
        text = text.replace(line, '')
    open(path, 'w').write(text)
PY

printf "\n\033[32mInstallation complete!\033[0m\n"
printf "\033[33mRecommended system packages for window control:\033[0m\n"
printf "  Debian/Ubuntu: sudo apt install xdotool wmctrl\n"
printf "  Fedora:        sudo dnf install xdotool wmctrl\n"
printf "  Arch:          sudo pacman -S xdotool wmctrl\n"
printf "\033[33mPrefer an X11 session (or XWayland). Wayland often blocks capture/input.\033[0m\n"
printf "\033[33mUse Sober (or another Roblox Linux client) before starting the macro.\033[0m\n"
printf "\033[32mStarting Fuzzy Macro...\033[0m\n"
cd "$PROJECT_ROOT"
exec bash "$PROJECT_ROOT/run_macro.sh"
