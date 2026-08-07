#!/usr/bin/env bash
set -euo pipefail

# Stop previous macro python processes started from this project if possible.
pkill -f "[Ff]uzzy-[Mm]acro.*/src/main.py" >/dev/null 2>&1 || true

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

# Prefer certifi CA bundle for Discord/aiohttp TLS
for py_dir in python3.9 python3.8 python3.7 python3 python; do
    cert_path="$VENV_PATH/lib/$py_dir/site-packages/certifi/cacert.pem"
    if [ -f "$cert_path" ]; then
        export SSL_CERT_FILE="$cert_path"
        break
    fi
done

cd "$PROJECT_ROOT/src"

if [ -x "$VENV_PATH/bin/python" ]; then
    printf "Activating virtual environment...\n"
    # shellcheck disable=SC1090
    source "$VENV_PATH/bin/activate"
    "$VENV_PATH/bin/python" --version
    exec "$VENV_PATH/bin/python" main.py
fi

printf "Virtual environment not found at %s\n" "$VENV_PATH"
printf "Starting dependency installer...\n"
cd "$PROJECT_ROOT"
exec bash "$PROJECT_ROOT/install_dependencies.sh"
