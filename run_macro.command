#!/bin/sh

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd) || exit 1
VENV_PATH="$HOME/fuzzy-macro-env"
MATCHER_DIR="$SCRIPT_DIR/src/modules/bitmap_matcher"

# Check the interpreter's architecture, which can differ from the host under Rosetta.
compatible_python() {
    metadata=$("$1" -c 'import sys, platform; print("%s.%s %s" % (sys.version_info[0], sys.version_info[1], platform.machine().lower()))' 2>/dev/null) || return 1
    python_ver=${metadata%% *}
    python_arch=${metadata#* }
    case "$python_ver" in
        3.7|3.8|3.9|3.10|3.11|3.12) ;;
        *) return 1 ;;
    esac
    case "$python_arch" in
        amd64) python_arch=x86_64 ;;
        aarch64) python_arch=arm64 ;;
        arm64|x86_64) ;;
        *) return 1 ;;
    esac
    version_tag=$(printf '%s' "$python_ver" | tr -d '.')
    [ -f "$MATCHER_DIR/bitmap_matcher_py${version_tag}_${python_arch}.so" ] \
        || [ -f "$MATCHER_DIR/bitmap_matcher_py${version_tag}.so" ]
}

PYTHON_BIN=""
if [ -e "$VENV_PATH" ] || [ -L "$VENV_PATH" ]; then
    if [ ! -x "$VENV_PATH/bin/python" ] || ! compatible_python "$VENV_PATH/bin/python"; then
        printf '%s\n' 'The macro virtual environment is broken or has no compatible bitmap matcher. Run install_dependencies.command to repair it.' >&2
        exit 1
    fi
    PYTHON_BIN="$VENV_PATH/bin/python"
    # Direct invocation uses venv packages; PATH also covers child Python processes.
    VIRTUAL_ENV="$VENV_PATH"
    PATH="$VENV_PATH/bin:$PATH"
    export VIRTUAL_ENV PATH
else
    for version in 3.12 3.11 3.10 3.9 3.8 3.7; do
        candidate=$(command -v "python$version") || continue
        if compatible_python "$candidate" && [ "$python_ver" = "$version" ]; then
            PYTHON_BIN="$candidate"
            break
        fi
    done
    if [ -z "$PYTHON_BIN" ]; then
        printf '%s\n' 'No supported Python with a shipped bitmap matcher was found. Run install_dependencies.command first.' >&2
        exit 1
    fi
fi

# Use the selected interpreter's certificate bundle rather than a stale venv version.
cert_path=$("$PYTHON_BIN" -c 'import certifi; print(certifi.where())' 2>/dev/null) || cert_path=""
if [ -n "$cert_path" ] && [ -f "$cert_path" ]; then
    SSL_CERT_FILE="$cert_path"
    export SSL_CERT_FILE
fi

cd "$SCRIPT_DIR/src" || exit 1
printf 'Loading macro with %s...\n' "$PYTHON_BIN"
# Run once and return the macro's exit status to the caller.
exec "$PYTHON_BIN" main.py
