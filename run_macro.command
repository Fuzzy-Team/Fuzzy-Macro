#!/bin/sh

VENV_NAME="fuzzy-macro-env"
VENV_PATH="$HOME/$VENV_NAME"

# Stop any Fuzzy Macro that is already running, from any copy of the macro, including
# Python child processes left behind by a macro that died. On macOS the venv's python
# re-launches as the framework Python, so the process shows up as ".../Python main.py"
# rather than under the venv path. A Fuzzy process is a Python main.py or
# multiprocessing child running in a folder next to a run_macro.command, which leaves
# other Python apps alone.
stop_fuzzy_macro() {
    fuzzy_pids=""
    for pid in $(pgrep -f "[Pp]ython[0-9.]* (main\.py|-c from multiprocessing)" 2>/dev/null); do
        cwd=$(lsof -a -p "$pid" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p')
        if [ -n "$cwd" ] && [ -f "$cwd/../run_macro.command" ]; then
            fuzzy_pids="$fuzzy_pids $pid"
        fi
    done
    fuzzy_pids=$(echo $fuzzy_pids)
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

version_at_least() {
    [ "$(printf '%s\n' "$1" "$2" | sort -V | head -n1)" = "$2" ]
}

python_ver="3.9"
if [ "$chip" = "i386" ]; then
	if version_at_least "$os_ver" "10.15.0"; then
		python_ver="3.8"
		printf "Correct python ver: 3.8\n"
	else
		python_ver="3.7"
		printf "Correct python ver: 3.7\n"
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
