#!/bin/sh

VENV_NAME="fuzzy-macro-env"
VENV_PATH="$HOME/$VENV_NAME"

# Stop only an existing Fuzzy Macro launched from this virtual environment.
# The old implementation killed every Python process on the machine.
stop_fuzzy_macro() {
    fuzzy_pids=$(pgrep -f "$VENV_PATH/bin/python.*main\.py" 2>/dev/null || true)
    if [ -z "$fuzzy_pids" ]; then
        return
    fi

    printf "Stopping existing Fuzzy Macro process(es): %s\n" "$fuzzy_pids"
    kill $fuzzy_pids 2>/dev/null || true
    sleep 1

    # Fall back to SIGKILL only if a stale process did not exit cleanly.
    for pid in $fuzzy_pids; do
        if kill -0 "$pid" 2>/dev/null; then
            kill -9 "$pid" 2>/dev/null || true
        fi
    done
}

stop_fuzzy_macro

# force Python to use certifi for SSL (fixes Discord/aiohttp on macOS)
for py_dir in python3.9 python3.8 python3.7 python3 python; do
    cert_path="$VENV_PATH/lib/$py_dir/site-packages/certifi/cacert.pem"
    if [ -f "$cert_path" ]; then
        export SSL_CERT_FILE="$cert_path"
        break
    fi
done

# get system information
chip=$(arch)
os_ver=$(sw_vers -productVersion)

python_ver="3.9"
if [ "$chip" = "i386" ]; then
    if echo -e "$os_ver\n10.15.0" | sort -V | tail -n1 | grep -Fq "10.15.0"; then
        python_ver="3.7"
        printf "Correct python ver: 3.7\n"
    elif echo -e "$os_ver\n12.0.0" | sort -V | tail -n1 | grep -Fq "12.0.0"; then
        python_ver="3.8"
        printf "Correct python ver: 3.8\n"
    fi
fi

cd "$(dirname "$0")"

runPython() {
    echo "Loading macro with $1..."
    $1 main.py
}

cd src
if [ -d "$VENV_PATH" ]; then
    source "$VENV_PATH/bin/activate"
    printf "activating virtual environment\n"
    "$VENV_PATH/bin/python" --version
    "$VENV_PATH/bin/python" main.py
else
    runPython python3.7
    runPython python3.8
    runPython python3.9
fi
