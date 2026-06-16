#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

VENV_NAME="${FUZZY_VENV_NAME:-fuzzy-macro-env}"
VENV_PATH="${FUZZY_VENV_PATH:-$HOME/$VENV_NAME}"

printf "Refreshing dependencies via install_dependencies.command...\n"
/bin/bash "./install_dependencies.command"

PYTHON="$VENV_PATH/bin/python"
export PYINSTALLER_CONFIG_DIR="${TMPDIR:-/tmp}/fuzzy-macro-pyinstaller"
export MACOSX_DEPLOYMENT_TARGET="${MACOSX_DEPLOYMENT_TARGET:-10.12}"

if [ -z "${FUZZY_TARGET_ARCH:-}" ]; then
    case "$(uname -m)" in
        arm64) FUZZY_TARGET_ARCH="arm64" ;;
        x86_64) FUZZY_TARGET_ARCH="x86_64" ;;
        *) FUZZY_TARGET_ARCH="$(uname -m)" ;;
    esac
    export FUZZY_TARGET_ARCH
fi

printf "Installing app build tools...\n"
if ! "$PYTHON" -c "import PyInstaller, webview" >/dev/null 2>&1; then
    "$PYTHON" -m pip install pyinstaller pywebview
else
    printf "PyInstaller and pywebview are already installed.\n"
fi

if [ "$FUZZY_TARGET_ARCH" = "universal2" ]; then
    PYTHON_EXEC=$("$PYTHON" -c 'import os, sys; print(os.path.realpath(sys.executable))')
    PYTHON_FILE=$(file "$PYTHON_EXEC")
    if ! printf "%s" "$PYTHON_FILE" | grep -q "x86_64"; then
        printf "\033[31;1mCannot build a universal2 app with this Python: %s\033[0m\n" "$PYTHON_FILE"
        printf "\033[31;1mInstall/use a universal2 Python 3.9, recreate %s, then run this build again.\033[0m\n" "$VENV_PATH"
        printf "\033[33;1mFor a local Apple Silicon-only build, run: FUZZY_TARGET_ARCH=arm64 ./build_app.command\033[0m\n"
        exit 1
    fi
    if ! printf "%s" "$PYTHON_FILE" | grep -q "arm64"; then
        printf "\033[31;1mCannot build a universal2 app with this Python: %s\033[0m\n" "$PYTHON_FILE"
        printf "\033[31;1mInstall/use a universal2 Python 3.9, recreate %s, then run this build again.\033[0m\n" "$VENV_PATH"
        printf "\033[33;1mFor a local Intel-only build, run: FUZZY_TARGET_ARCH=x86_64 ./build_app.command\033[0m\n"
        exit 1
    fi
fi

if [ "$FUZZY_TARGET_ARCH" = "arm64" ]; then
    export MACOSX_DEPLOYMENT_TARGET="${FUZZY_ARM64_DEPLOYMENT_TARGET:-13.0}"
fi

printf "Building Fuzzy Macro.app for %s with macOS deployment target %s...\n" "$FUZZY_TARGET_ARCH" "$MACOSX_DEPLOYMENT_TARGET"
"$PYTHON" -m PyInstaller --clean --noconfirm fuzzy_macro_app.spec

if [ -n "${FUZZY_CODESIGN_IDENTITY:-}" ]; then
    printf "Signing Fuzzy Macro.app with identity: %s\n" "$FUZZY_CODESIGN_IDENTITY"
    CODESIGN_ARGS=(--force --deep --strict --options runtime --sign "$FUZZY_CODESIGN_IDENTITY")
    if [ "${FUZZY_CODESIGN_TIMESTAMP:-0}" = "1" ]; then
        CODESIGN_ARGS+=(--timestamp)
    fi
    if [ -n "${FUZZY_ENTITLEMENTS_FILE:-}" ]; then
        CODESIGN_ARGS+=(--entitlements "$FUZZY_ENTITLEMENTS_FILE")
    fi
    codesign "${CODESIGN_ARGS[@]}" "dist/Fuzzy Macro.app"
else
    printf "\033[33;1mNo FUZZY_CODESIGN_IDENTITY set; macOS may ask for permissions again after each rebuild.\033[0m\n"
fi

printf "\nBuild complete: %s/dist/Fuzzy Macro.app\n" "$(pwd)"
