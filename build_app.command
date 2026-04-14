#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

VENV_NAME="fuzzy-macro-env"
VENV_PATH="$HOME/$VENV_NAME"

if [ ! -x "$VENV_PATH/bin/python" ]; then
    printf "Virtual environment not found. Running dependency installer first...\n"
    /bin/bash "./install_dependencies.command"
fi

PYTHON="$VENV_PATH/bin/python"
export PYINSTALLER_CONFIG_DIR="${TMPDIR:-/tmp}/fuzzy-macro-pyinstaller"

printf "Installing app build tools...\n"
if ! "$PYTHON" -c "import PyInstaller, webview" >/dev/null 2>&1; then
    "$PYTHON" -m pip install pyinstaller pywebview
else
    printf "PyInstaller and pywebview are already installed.\n"
fi

printf "Building Fuzzy Macro.app...\n"
"$PYTHON" -m PyInstaller --clean --noconfirm fuzzy_macro_app.spec

printf "\nBuild complete: %s/dist/Fuzzy Macro.app\n" "$(pwd)"
